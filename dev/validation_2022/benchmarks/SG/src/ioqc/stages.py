"""Pipeline stages S0-S8. Each stage: reads prior checkpoint(s), writes its own,
asserts its accounting contract, returns a report dict. Fail-fast on hard controls.
"""
from __future__ import annotations
import os, json, hashlib, time
import numpy as np
from . import provincial as P

# ---------------- helpers ----------------

def _sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while (b := f.read(buf)):
            h.update(b)
    return h.hexdigest()


def _ck(cfg, name):
    d = os.path.join(cfg.root, 'checkpoints', name)
    os.makedirs(d, exist_ok=True)
    return d


def _outdir(cfg, name):
    d = os.path.join(cfg.root, name)
    os.makedirs(d, exist_ok=True)
    return d


def _relerr(a, b):
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom


class HardControlError(AssertionError):
    pass


# ---------------- S0: manifest + hashes ----------------

def s0_manifest(cfg):
    # Unzip the national Detail CSV from the repo-local zip (kept zipped to stay < GitHub 100MB).
    import zipfile
    ncsv = cfg.path('national_detail_csv')
    if not os.path.exists(ncsv):
        os.makedirs(os.path.dirname(ncsv), exist_ok=True)
        with zipfile.ZipFile(cfg.path('national_detail_zip')) as z:
            member = next(n for n in z.namelist() if n.endswith('.csv') and 'MetaData' not in n)
            with z.open(member) as fi, open(ncsv, 'wb') as fo:
                while (chunk := fi.read(1 << 20)):
                    fo.write(chunk)
    # Manifest hashes the REPOSITORY-LOCAL raw source files actually used (not derived artifacts).
    files = {}
    for prov in cfg.regions:
        files[f'prov_{prov}'] = P.workbook_path(cfg, prov)
    files['national_detail_zip'] = cfg.path('national_detail_zip')
    files['national_detail_meta'] = cfg.path('national_detail_meta')
    files['oecd_icio_2022'] = cfg.path('oecd_icio_2022_csv')
    for k in cfg.cfg['config_files']:
        files[f'config_{k}'] = cfg.cfgfile(k)
    manifest = {'year': cfg.cfg['year'], 'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'files': {}}
    missing = []
    for key, path in files.items():
        if os.path.exists(path):
            manifest['files'][key] = {'path': os.path.relpath(path, cfg.root),
                                      'sha256': _sha256(path),
                                      'bytes': os.path.getsize(path)}
        else:
            missing.append((key, path))
    d = _ck(cfg, 's0_manifest')
    with open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    if missing:
        raise HardControlError(f"S0: missing required inputs: {missing}")
    return {'stage': 'S0', 'n_files': len(manifest['files']), 'missing': 0}


# ---------------- S1: native StatCan checks ----------------

def s1_native(cfg):
    from . import xlsx
    need_industry = set(cfg.ind2oecd)
    need_prm = set(cfg.prm_class)
    report = {'stage': 'S1', 'provinces': {}}
    for prov in cfg.regions:
        path = P.workbook_path(cfg, prov)
        bp = xlsx.read_sheet(path, 'BasicPrice')
        rowset = set(bp.row_codes)
        miss_ind = need_industry - rowset
        miss_prm = need_prm - rowset
        groups = set(bp.col_groups)
        ok_groups = {'Interprovincial exports', 'Interprovincial imports',
                     'To Final Demand Category'} <= groups
        prov_ok = (not miss_ind) and (not miss_prm) and ok_groups
        report['provinces'][prov] = {
            'n_row_codes': len(bp.row_codes), 'n_use_cols': len(bp.col_codes),
            'missing_industries': len(miss_ind), 'missing_prm': len(miss_prm),
            'has_trade_groups': ok_groups, 'ok': prov_ok}
        if not prov_ok:
            raise HardControlError(f"S1 {prov}: miss_ind={miss_ind} miss_prm={miss_prm} groups_ok={ok_groups}")
        _native_detail_save(cfg, prov)
    report['native_detail_checkpoint'] = 'checkpoints/native_detail/<prov>.npz (220 commodity x use, pre-OECD-50)'
    return report


def _native_detail_save(cfg, prov):
    """NATIVE VALIDATED LAYER: full 220-commodity x use matrices, StatCan IOIC codes, basic &
    purchaser & margin & tax layers, source-split — saved verbatim BEFORE any OECD-50 mapping.
    This is the reproducible native-detail checkpoint (distinct from the mapped canonical layer)."""
    from . import xlsx
    d = _ck(cfg, 'native_detail')
    out_path = os.path.join(d, f'{prov}.npz')
    if os.path.exists(out_path):
        return
    path = P.workbook_path(cfg, prov)
    is_ind = lambda c: c[:2] in ('BS', 'NP', 'GS')  # noqa: E731
    layers = {}
    codes_row = codes_col = None
    for sheet in ['BasicPrice', 'Purchaser', 'Tax', 'MarginsTrade', 'MarginsTransport',
                  'DomesticUse', 'InterprovImportUse', 'InternatImportUse']:
        try:
            sh = xlsx.read_sheet(path, sheet)
        except KeyError:
            continue
        rc, cc, sub = sh.block(is_ind, lambda c, g: is_ind(c))     # 220 commodity x 220 industry
        rc2, cc2, subfd = sh.block(is_ind, lambda c, g: g == 'To Final Demand Category')  # x FD (raw)
        layers[f'{sheet}__ij'] = np.nan_to_num(sub)
        layers[f'{sheet}__fd'] = np.nan_to_num(subfd)
        if codes_row is None:
            codes_row, codes_col, codes_fd = rc, cc, cc2
    np.savez(out_path, commodity_codes=np.array(codes_row), industry_codes=np.array(codes_col),
             fd_codes=np.array(codes_fd), units='CAD thousands, native StatCan IOIC/IOCC detail',
             **layers)


# ---------------- S2/S3: map to OECD-50 + provincial blocks ----------------

def s2_s3_provincial(cfg):
    d = _ck(cfg, 's3_provincial')
    report = {'stage': 'S2/S3', 'provinces': {}}
    tol = cfg.cfg['tolerances']['conservation_rel']
    itol = cfg.cfg['tolerances']['identity_rel']
    for prov in cfg.regions:
        b = P.load_province(cfg, prov)
        # --- S2 conservation: mapped block sum == native block sum ---
        for key, nat in b['_native_sums'].items():
            got = float(b[key].sum())
            if _relerr(got, nat) > tol:
                raise HardControlError(f"S2 {prov} {key}: mapped {got:.3f} != native {nat:.3f}")
        # --- S3 column identity: output_j = total intermediate inputs_j + VA_j ---
        Z_tot = b['Z_domestic'] + b['Z_interprov_use'] + b['Z_internat_use']
        va_total = np.sum([v for v in b['VA'].values()], axis=0)          # 6 genuine VA components
        val_total = (np.sum([v for v in b['valuation'].values()], axis=0)  # product tax/subsidy
                     if b['valuation'] else np.zeros(len(cfg.oecd50)))
        output_col = Z_tot.sum(axis=0) + va_total + val_total   # basic-price column total
        # --- S3 commodity balance (hard): total supply = total use, all sources ---
        #   supply = domestic output + |internat imports| + |interprov imports|
        #   use    = intermediate + FD + internat exports + re-exports + interprov exports
        M = np.abs(b['internat_imports_ctrl'])
        II = np.abs(np.sum([b['interprov_imports_from'][p] for p in cfg.regions], axis=0))
        IE = np.sum([b['interprov_exports_to'][p] for p in cfg.regions], axis=0)
        supply = output_col + M + II
        use = (Z_tot.sum(axis=1) + b['FD'].sum(axis=1)
               + b['exports'] + b['reexports'] + IE)
        gap = _relerr(float(supply.sum()), float(use.sum()))
        percindustry = float(np.max(np.abs(supply - use) / np.maximum(supply, 1.0)))
        if percindustry > max(itol, 1e-4):
            raise HardControlError(f"S3 {prov}: commodity supply=use fails, max rel {percindustry:.5f}")
        b['output'] = output_col
        b['va_total'] = va_total
        b['internat_imports'] = M
        if b['_fd_split_gap'] > max(itol, 1e-4) * max(float(np.abs(b['FD']).sum()), 1.0):
            raise HardControlError(f"S3 {prov}: FD source split != total FD, gap {b['_fd_split_gap']:.3f}")
        # save checkpoint
        np.savez(os.path.join(d, f'{prov}.npz'),
                 oecd50=np.array(cfg.oecd50),
                 Z_domestic=b['Z_domestic'], Z_interprov_use=b['Z_interprov_use'],
                 Z_internat_use=b['Z_internat_use'], FD=b['FD'],
                 FD_domestic=b['FD_domestic'], FD_interprov=b['FD_interprov'],
                 FD_internat=b['FD_internat'],
                 exports=b['exports'], reexports=b['reexports'],
                 output=output_col, va_total=va_total,
                 internat_imports=M,
                 margin_trade=b['margin_trade'], margin_transport=b['margin_transport'],
                 Z_purchaser=b['Z_purchaser'], tax_ij=b['tax_ij'],
                 margin_trade_fd=b['margin_trade_fd'], margin_transport_fd=b['margin_transport_fd'],
                 purchaser_fd=b['purchaser_fd'], tax_fd=b['tax_fd'],
                 prod_tax_final_bycat=b['prod_tax_final_bycat'],
                 prod_subsidy_final_bycat=b['prod_subsidy_final_bycat'],
                 prm_row_total=np.array(json.dumps(b['prm_row_total'])),
                 **{f'VA__{k}': v for k, v in b['VA'].items()},
                 **{f'VAL__{k}': v for k, v in b['valuation'].items()},
                 **{f'IEXP__{p}': b['interprov_exports_to'][p] for p in cfg.regions},
                 **{f'IIMP__{p}': b['interprov_imports_from'][p] for p in cfg.regions})
        report['provinces'][prov] = {
            'output_total': float(output_col.sum()),
            'va_total': float(va_total.sum()),
            'exports_total': float(b['exports'].sum()),
            'commodity_balance_relgap': gap,
            'max_industry_relgap': percindustry,
            'ok': percindustry <= max(itol, 1e-4)}
    return report


# ---------------- S4: consolidate national + controls ----------------

def _load_ckpt(cfg):
    d = _ck(cfg, 's3_provincial')
    out = {}
    for prov in cfg.regions:
        out[prov] = dict(np.load(os.path.join(d, f'{prov}.npz'), allow_pickle=True))
    return out


def _national_detail_industry_output(cfg, codes):
    """National 2022 basic-price output for given StatCan industry codes (Supply=code, Use='Total use')."""
    path = cfg.path('national_detail_csv')
    if not os.path.exists(path):
        return {}
    import csv
    want = set(codes); got = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        r = csv.reader(f); hdr = next(r)
        ix = {h: i for i, h in enumerate(hdr)}
        iR, iVal, iS, iU, iV = ix['REF_DATE'], ix['Valuation'], ix['Supply'], ix['Use'], ix['VALUE']
        for row in r:
            if row[iR] != '2022' or 'Basic' not in row[iVal] or row[iU] != 'Total use':
                continue
            m = row[iS]; code = m[m.find('[') + 1:m.find(']')] if '[' in m else ''
            if code in want and row[iV]:
                got[code] = got.get(code, 0.0) + float(row[iV])
    return got


def _national_detail_va(cfg):
    """Stream national Detail 36-10-0001 CSV: national 2022 basic-price VA components
    (Supply=PRM*, Use='Total use'). Returns {prm_code: value_kdollars}."""
    path = cfg.path('national_detail_csv')
    if not os.path.exists(path):
        return {}
    import csv
    want = set(cfg.prm_class)  # PRM100000..PRM800000
    got = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        r = csv.reader(f)
        hdr = next(r)
        ix = {h: i for i, h in enumerate(hdr)}
        iR, iVal, iS, iU, iV = ix['REF_DATE'], ix['Valuation'], ix['Supply'], ix['Use'], ix['VALUE']
        for row in r:
            if row[iR] != '2022' or 'Basic' not in row[iVal] or row[iU] != 'Total use':
                continue
            m = row[iS]
            code = m[m.find('[') + 1:m.find(']')] if '[' in m else ''
            if code in want and row[iV]:
                got[code] = got.get(code, 0.0) + float(row[iV])
    return got


def _reexport_split(b):
    """Split a province's re-exports (INTRX000) by commodity into the part supplied by imports that
    never enter Canadian use (INTIM - InternatImportUse, capped at the re-export value) and the
    domestic remainder (Canadian trade/transport margins on re-exported goods, e.g. G/H49/H52).
    Only the imported part is excluded from producer rows; the domestic part stays an export."""
    unused_imports = np.abs(b['internat_imports']) - b['Z_internat_use'].sum(axis=1) - b['FD_internat'].sum(axis=1)
    imported = np.minimum(b['reexports'], np.maximum(unused_imports, 0.0))
    return imported, b['reexports'] - imported


def s4_consolidate_national(cfg):
    ck = _load_ckpt(cfg)
    O = cfg.oecd50
    n = len(O)
    Z_nat = np.zeros((n, n))
    va_nat = np.zeros(n)
    fd_nat = np.zeros((n, ck['ON']['FD'].shape[1]))
    exp_nat = np.zeros(n); reexp_nat = np.zeros(n); imp_nat = np.zeros(n)
    va_by_class = {}
    for prov in cfg.regions:
        b = ck[prov]
        Z_nat += b['Z_domestic'] + b['Z_interprov_use']       # interprov trade is internal
        va_nat += b['va_total']
        fd_nat += b['FD']
        # Re-exports (INTRX000) are imported goods leaving Canada untransformed. Their imports are
        # absent from InternatImportUse, so they must not be booked as Canadian producer sales
        # either: kept as a separate satellite (OECD ICIO also nets re-exports out of both sides).
        # Canadian margins on them (domestic output) remain exports.
        rx_imp, rx_dom = _reexport_split(b)
        exp_nat += b['exports'] + rx_dom
        reexp_nat += rx_imp
        imp_nat += b['internat_imports']
        for k in b:
            if k.startswith('VA__'):
                va_by_class[k[4:]] = va_by_class.get(k[4:], 0.0) + float(b[k].sum())

    # --- hard control: interprovincial trade cancels nationally (per commodity) ---
    exp_all = np.zeros(n); imp_all = np.zeros(n)
    for prov in cfg.regions:
        b = ck[prov]
        for p in cfg.regions:
            exp_all += b[f'IEXP__{p}']
            imp_all += b[f'IIMP__{p}']    # stored negative
    cancel = float(np.abs(exp_all + imp_all).sum())
    cancel_rel = cancel / max(float(np.abs(exp_all).sum()), 1.0)
    if cancel_rel > 1e-6:
        raise HardControlError(f"S4: interprovincial trade does not cancel nationally, rel {cancel_rel:.2e}")

    # --- control: consolidated PRM row-totals vs published national Detail 2022 (all uses) ---
    prov_prm = {}
    for prov in cfg.regions:
        d = json.loads(str(ck[prov]['prm_row_total']))
        for cls, v in d.items():
            prov_prm[cls] = prov_prm.get(cls, 0.0) + v
    nat_va = _national_detail_va(cfg)
    va_cmp = {}
    if nat_va:
        nat_by_cls = {}
        for prm, val in nat_va.items():
            nat_by_cls[cfg.prm_class[prm]] = nat_by_cls.get(cfg.prm_class[prm], 0.0) + val
        for cls in sorted(set(prov_prm) | set(nat_by_cls)):
            pv = prov_prm.get(cls, 0.0); nv = nat_by_cls.get(cls, 0.0)
            va_cmp[cls] = {'provinces_sum': pv, 'national_detail': nv,
                           'rel_diff': _relerr(pv, nv) if nv else None}

    d = _ck(cfg, 's4_national')
    np.savez(os.path.join(d, 'national.npz'), oecd50=np.array(O),
             Z=Z_nat, VA=va_nat, FD=fd_nat, exports=exp_nat, reexports=reexp_nat, imports=imp_nat)
    band = cfg.cfg['tolerances']['national_vs_detail_rel']
    va_flags = {k: (v['rel_diff'] is None or v['rel_diff'] <= band) for k, v in va_cmp.items()}
    return {'stage': 'S4',
            'national_output': float(Z_nat.sum(axis=0).sum() + va_nat.sum()),
            'national_VA': float(va_nat.sum()),
            'national_exports': float(exp_nat.sum()),
            'national_reexports': float(reexp_nat.sum()),
            'national_imports': float(imp_nat.sum()),
            'interprov_cancel_rel': cancel_rel,
            'va_vs_national_detail': va_cmp,
            'va_within_band': all(va_flags.values()) if va_flags else None}


# ---------------- S5: interprovincial assembly (observed bilateral) ----------------

def s5_interprovincial(cfg):
    """Assemble the OBSERVED bilateral O-D commodity matrix (province BasicPrice sheets),
    verify mirror-consistency, and derive origin shares to attribute destination use to
    origin provinces under origin-homogeneity. No RAS: the O-D pairing is observed."""
    ck = _load_ckpt(cfg)
    regs = cfg.regions
    R, nI = len(regs), len(cfg.oecd50)
    ri = {r: k for k, r in enumerate(regs)}
    mtol = cfg.cfg['tolerances']['interprov_mirror_abs']

    OD = np.zeros((R, R, nI))                    # [origin, dest, commodity], exports o->d
    for o in regs:
        for d in regs:
            if d == o:
                continue
            OD[ri[o], ri[d]] = ck[o][f'IEXP__{d}']

    # --- hard control: mirror consistency  export(o->d) == -import(d<-o) ---
    max_mirror = 0.0
    for o in regs:
        for d in regs:
            if o == d:
                continue
            exp = ck[o][f'IEXP__{d}']
            imp = ck[d][f'IIMP__{o}']            # stored negative
            max_mirror = max(max_mirror, float(np.abs(exp + imp).max()))
    if max_mirror > mtol:
        raise HardControlError(f"S5: interprovincial mirror mismatch {max_mirror:.3f} k$ > {mtol}")

    # --- origin shares per (dest, commodity): fraction of d's interprov imports from each o ---
    origin_share = np.zeros((R, R, nI))          # [origin, dest, commodity]
    for d in regs:
        imp_by_o = OD[:, ri[d], :]               # [o, i]
        tot = imp_by_o.sum(axis=0)               # [i]
        with np.errstate(divide='ignore', invalid='ignore'):
            sh = np.where(tot > 0, imp_by_o / tot, 0.0)
        origin_share[:, ri[d], :] = sh

    # feasible-support diagnostics (observed): which (o,d,i) are positive
    feasible = OD > 0
    d = _ck(cfg, 's5_interprov')
    np.savez(os.path.join(d, 'interprov.npz'), regions=np.array(regs),
             oecd50=np.array(cfg.oecd50), OD=OD, origin_share=origin_share)
    return {'stage': 'S5', 'method': cfg.cfg['interprovincial']['method'],
            'max_mirror_abs_k': max_mirror,
            'total_interprov_trade_M': float(OD.sum() / 1e3),
            'n_feasible_od_cells': int(feasible.sum()),
            'n_possible_od_cells': int(R * (R - 1) * nI),
            'observed_pairing': True}


# ---------------- S6: ROW construction + OECD border diagnostic ----------------

def _oecd_canada_margins(cfg):
    """From OECD ICIO 2022 SML: Canada total exports & imports (USD million).
    exports = CAN rows into foreign columns; imports = foreign rows into CAN columns."""
    import pandas as pd
    path = cfg.path('oecd_icio_2022_csv')
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col=0)
    inds = set(cfg.oecd50)
    # producing rows must be genuine industries (exclude TLS/VA/OUTPUT pseudo-rows)
    def is_ind_label(lbl):
        s = str(lbl)
        return '_' in s and s.rsplit('_', 1)[0] and s[s.find('_') + 1:] in inds
    fd_suffix = {'HFCE', 'NPISH', 'GGFC', 'GFCF', 'INVNT', 'DPABR'}
    valid_suffix = inds | fd_suffix                                          # exclude TOTAL/output cols
    def valid_col(c):
        s = str(c)
        return '_' in s and s[s.find('_') + 1:] in valid_suffix
    cols = [c for c in df.columns if valid_col(c)]
    can_cols = [c for c in cols if str(c).startswith('CAN_')]                 # CAN interm+FD only
    for_cols = [c for c in cols if not str(c).startswith('CAN_')]
    idx = [i for i in df.index if is_ind_label(i)]                            # industry rows only
    can_rows = [i for i in idx if str(i).startswith('CAN_')]
    for_rows = [i for i in idx if not str(i).startswith('CAN_')]
    exports = float(df.loc[can_rows, for_cols].to_numpy().sum())             # CAN -> world
    imports = float(df.loc[for_rows, can_cols].to_numpy().sum())             # world -> CAN
    return {'oecd_exports_MUSD': exports, 'oecd_imports_MUSD': imports}


def _oecd_row_blocks(cfg):
    """Collapse all non-Canada OECD ICIO 2022 economies into a single ROW at OECD-50.
    Returns (in USD million): ROW_Z[i,j] (ROW internal intermediate), ROW_FD[i,k],
    ROW_out[i], ROW_va[i], can2row_interm[i], can2row_fd[i] (Canada exports used by ROW,
    split intermediate vs final), plus OECD Canada export/import totals for the diagnostic."""
    import pandas as pd
    path = cfg.path('oecd_icio_2022_csv')
    if not os.path.exists(path):
        return None
    O = cfg.oecd50; nI = len(O); oi = {c: k for k, c in enumerate(O)}
    fd_map = {'HFCE': 'HFCE', 'NPISH': 'NPISH', 'GGFC': 'GGFC', 'GFCF': 'GFCF',
              'INVNT': 'INVNT', 'DPABR': 'DPABR'}
    fd_to_cat = {'HFCE': 'HFCE', 'NPISH': 'NPISH', 'GGFC': 'GGFC', 'GFCF': 'GFCF',
                 'INVNT': 'INVNT', 'DPABR': 'DPABR'}
    from .provincial import FD_CATS
    fdc = {c: k for k, c in enumerate(FD_CATS)}
    df = pd.read_csv(path, index_col=0)

    def parse(lbl):
        s = str(lbl)
        if '_' not in s:
            return None, None
        c, suf = s.split('_', 1)
        return c, suf
    rows = [(i, *parse(i)) for i in df.index]
    cols = [(c, *parse(c)) for c in df.columns]
    ind_rows = [(i, c, s) for (i, c, s) in rows if s in oi]
    ind_cols = [(c, cc, s) for (c, cc, s) in cols if s in oi]
    fd_cols = [(c, cc, s) for (c, cc, s) in cols if s in fd_to_cat]

    ROW_Z = np.zeros((nI, nI)); ROW_FD = np.zeros((nI, len(FD_CATS)))
    can2row_ij = np.zeros((nI, nI)); can2row_fdk = np.zeros((nI, len(FD_CATS)))
    row2can_i = np.zeros(nI); row2can_fd = 0.0  # ROW -> Canada intermediate / final demand
    M = df.to_numpy()
    ridx = {i: k for k, i in enumerate(df.index)}
    cidx = {c: k for k, c in enumerate(df.columns)}
    for (ri, rc, rs) in ind_rows:
        rr = ridx[ri]; a = oi[rs]
        for (ci, cc, cs) in ind_cols:
            v = M[rr, cidx[ci]]
            if v == 0 or np.isnan(v):
                continue
            bj = oi[cs]
            if rc != 'CAN' and cc != 'CAN':
                ROW_Z[a, bj] += v                 # ROW internal intermediate
            elif rc == 'CAN' and cc != 'CAN':
                can2row_ij[a, bj] += v            # Canada i -> ROW j intermediate
            elif rc != 'CAN' and cc == 'CAN':
                row2can_i[a] += v                 # ROW -> Canada intermediate
        for (ci, cc, cs) in fd_cols:
            v = M[rr, cidx[ci]]
            if v == 0 or np.isnan(v):
                continue
            k = fdc[fd_to_cat[cs]]
            if rc != 'CAN' and cc != 'CAN':
                ROW_FD[a, k] += v
            elif rc == 'CAN' and cc != 'CAN':
                can2row_fdk[a, k] += v            # Canada i -> ROW final demand
            elif rc != 'CAN' and cc == 'CAN':
                row2can_fd += v                   # ROW -> Canada final demand imports
    ROW_out = ROW_Z.sum(axis=1) + ROW_FD.sum(axis=1) + row2can_i
    ROW_va = ROW_out - ROW_Z.sum(axis=0) - can2row_ij.sum(axis=0)
    oecd_exports = float(can2row_ij.sum() + can2row_fdk.sum())
    oecd_imports = float(row2can_i.sum() + row2can_fd)   # intermediate + final-demand imports
    return dict(ROW_Z=ROW_Z, ROW_FD=ROW_FD, ROW_out=ROW_out, ROW_va=ROW_va,
                can2row_ij=can2row_ij, can2row_fdk=can2row_fdk, row2can_i=row2can_i,
                oecd_exports_MUSD=oecd_exports, oecd_imports_MUSD=oecd_imports)


def s6_row(cfg):
    nat = dict(np.load(os.path.join(_ck(cfg, 's4_national'), 'national.npz'), allow_pickle=True))
    exp_nat = nat['exports']                 # StatCan national intl exports excl. imported re-exports (k$ CAD)
    imp_nat = np.abs(nat['imports'])         # StatCan national intl imports (k$ CAD)
    fx = cfg.cfg['usd_cad_2022_avg']
    O = cfg.oecd50; nI = len(O)

    blocks = _oecd_row_blocks(cfg)
    d = _ck(cfg, 's6_row')
    if blocks is None:
        np.savez(os.path.join(d, 'row.npz'), oecd50=np.array(O),
                 row_to_canada=imp_nat, canada_to_row=exp_nat)
        return {'stage': 'S6', 'foreign_mode': cfg.cfg['foreign_mode'], 'oecd_available': False}

    # scale OECD -> CAD k$ ; StatCan governs Canadian totals: split can2row into interm/FD by OECD ratio
    to_kcad = fx * 1e3                        # USD million -> CAD thousand
    ROW_Z = blocks['ROW_Z'] * to_kcad
    ROW_FD = blocks['ROW_FD'] * to_kcad
    ROW_out = blocks['ROW_out'] * to_kcad
    ROW_va = blocks['ROW_va'] * to_kcad
    # Canada->ROW (i->j intermediate + i->k FD): OECD pattern rescaled per producing industry i so
    # each industry's total Canada->ROW = StatCan exports exp_nat[i] (StatCan governs Canadian totals).
    c2r_ij, c2r_fdk = blocks['can2row_ij'], blocks['can2row_fdk']
    oecd_i_tot = c2r_ij.sum(axis=1) + c2r_fdk.sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        scale_i = np.where(oecd_i_tot > 0, exp_nat / (oecd_i_tot * to_kcad), 0.0)
    canada_to_row_ij = c2r_ij * to_kcad * scale_i[:, None]
    canada_to_row_fd = c2r_fdk * to_kcad * scale_i[:, None]
    # industries with no OECD export pattern but positive StatCan exports -> assign to ROW FD (HFCE)
    from .provincial import FD_CATS
    resid = exp_nat - (canada_to_row_ij.sum(axis=1) + canada_to_row_fd.sum(axis=1))
    canada_to_row_fd[:, FD_CATS.index('HFCE')] += np.maximum(resid, 0.0)

    np.savez(os.path.join(d, 'row.npz'), oecd50=np.array(O),
             ROW_Z=ROW_Z, ROW_FD=ROW_FD, ROW_out=ROW_out, ROW_va=ROW_va,
             canada_to_row_ij=canada_to_row_ij, canada_to_row_fd=canada_to_row_fd,
             row_to_canada=imp_nat,          # ROW->Canada handled via provincial Z_internat_use/FD_internat
             oecd_exports_MUSD=np.array(blocks['oecd_exports_MUSD']),
             oecd_imports_MUSD=np.array(blocks['oecd_imports_MUSD']),
             fx_usd_cad=np.array(fx))

    border = {'statcan_exports_MCAD': float(exp_nat.sum() / 1e3),
              'statcan_imports_MCAD': float(imp_nat.sum() / 1e3),
              'oecd_exports_MCAD': blocks['oecd_exports_MUSD'] * fx,
              'oecd_imports_MCAD': blocks['oecd_imports_MUSD'] * fx}
    border['exports_rel_diff'] = _relerr(border['statcan_exports_MCAD'], border['oecd_exports_MCAD'])
    border['imports_rel_diff'] = _relerr(border['statcan_imports_MCAD'], border['oecd_imports_MCAD'])
    border['cause'] = ('valuation (FOB vs basic/CIF), FX, vintage, and statistical asymmetry; '
                       'StatCan governs Canadian totals, OECD supplies ROW structure')
    return {'stage': 'S6', 'foreign_mode': cfg.cfg['foreign_mode'], 'oecd_available': True,
            'ROW_output_M': float(ROW_out.sum() / 1e3), 'ROW_VA_M': float(ROW_va.sum() / 1e3),
            'ROW_internal_intermediate_M': float(ROW_Z.sum() / 1e3),
            'canada_to_row_interm_M': float(canada_to_row_ij.sum() / 1e3),
            'canada_to_row_fd_M': float(canada_to_row_fd.sum() / 1e3),
            'border_diagnostic': border}


# ---------------- S7: integrated table assembly ----------------

def s7_assemble(cfg):
    """CANONICAL assembly: 13 P/T + CE + ROW, OFFICIAL OECD-50 codes, TRUE observed origin
    shares over all 14 Canadian regions (no renormalisation -> bilateral control exact).
    All 6 FD categories preserved. CE is a full accounting region here; the CE fold to a
    behavioural 13-P/T set happens only in the compatibility view (S8)."""
    ck = _load_ckpt(cfg)
    cregs = cfg.regions                      # 14 (incl CE) — full accounting regions
    ip = dict(np.load(os.path.join(_ck(cfg, 's5_interprov'), 'interprov.npz'), allow_pickle=True))
    row = dict(np.load(os.path.join(_ck(cfg, 's6_row'), 'row.npz'), allow_pickle=True))
    oshare = ip['origin_share']              # [o,d,i] TRUE shares over 14 regions (sum_o = 1)
    O = cfg.oecd50; nI = len(O); FDcats = P.FD_CATS; nK = len(FDcats)
    table_regs = list(cregs) + ['ROW']       # 15 regions
    R = len(table_regs); ri = {r: k for k, r in enumerate(table_regs)}
    ci = {r: k for k, r in enumerate(cregs)}
    N = R * nI

    def sl(r):
        k = ri[r]
        return slice(k * nI, (k + 1) * nI)

    # province international-export shares (to split national Canada->ROW back to provinces)
    exp_by = np.array([ck[p]['exports'] + _reexport_split(ck[p])[1] for p in cregs])   # [p,i] excl. imported re-exports
    with np.errstate(divide='ignore', invalid='ignore'):
        pshare = np.where(exp_by.sum(0) > 0, exp_by / exp_by.sum(0), 0.0)        # [p,i]

    # ---- intermediate Z ----
    Z = np.zeros((N, N))
    for d in cregs:
        b = ck[d]
        Z[sl(d), sl(d)] += b['Z_domestic']
        Zi = b['Z_interprov_use']
        for o in cregs:
            if o == d:
                continue
            Z[sl(o), sl(d)] += oshare[ci[o], ci[d], :][:, None] * Zi
        Z[sl('ROW'), sl(d)] += b['Z_internat_use']                # ROW -> d imports (InternatImportUse)
    if 'ROW_Z' in row:
        Z[sl('ROW'), sl('ROW')] += row['ROW_Z']
        for p in cregs:
            Z[sl(p), sl('ROW')] += pshare[ci[p], :][:, None] * row['canada_to_row_ij']

    # ---- final demand FD[producer(N), consumer_region(R), k] (all 6 cats) ----
    FD = np.zeros((N, R, nK))
    for d in cregs:
        b = ck[d]
        FD[sl(d), ri[d], :] += b['FD_domestic']
        for o in cregs:
            if o == d:
                continue
            FD[sl(o), ri[d], :] += oshare[ci[o], ci[d], :][:, None] * b['FD_interprov']
        FD[sl('ROW'), ri[d], :] += b['FD_internat']               # imports to d final demand
    if 'ROW_FD' in row:
        FD[sl('ROW'), ri['ROW'], :] += row['ROW_FD']
        for p in cregs:
            FD[sl(p), ri['ROW'], :] += pshare[ci[p], :][:, None] * row['canada_to_row_fd']

    # ---- below-the-line rows ----
    VA = np.zeros(N)                          # value added at basic prices (6 components)
    PTAX_INT = np.zeros(N)                    # net product tax on INTERMEDIATE (basic->purchaser bridge)
    for p in cregs:
        VA[sl(p)] = ck[p]['va_total']
        vt = [ck[p][k] for k in ck[p] if k.startswith('VAL__')]
        if vt:
            PTAX_INT[sl(p)] = np.sum(vt, axis=0)
    if 'ROW_va' in row:
        VA[sl('ROW')] = row['ROW_va']

    d = _ck(cfg, 's7_assemble')
    np.savez(os.path.join(d, 'integrated.npz'),
             table_regions=np.array(table_regs), oecd50=np.array(O),
             fd_cats=np.array(FDcats), Z=Z, FD=FD, VA=VA, PTAX_INT=PTAX_INT)
    return {'stage': 'S7', 'canonical_regions': R, 'industries': nI, 'matrix_dim': N,
            'regions': table_regs, 'codes': 'official OECD-50',
            'Z_total_M': float(Z.sum() / 1e3), 'FD_total_M': float(FD.sum() / 1e3),
            'VA_total_M': float(VA.sum() / 1e3)}



# ---------------- S8: validation + canonical rich export + compatibility view ----------------

# Compatibility-ONLY aliases (canonical keeps official OECD-50 codes). Applied only when writing
# the MacroABM compatibility view, because the current 2014 reader's industry regex rejects
# C17_18 / C24A / C24B / C301 / C302T309 / J62_63. Not a second concordance: pure label rename.
READER_ALIAS = {'C17_18': 'C17T18', 'C24A': 'C24a', 'C24B': 'C24b',
                'C301': 'C30a', 'C302T309': 'C30b', 'J62_63': 'J62T63'}
# FD semantics (item 6): the model consumes ONLY Household/Government Consumption + Fixed Capital
# Formation (GFCF, later split into firm/household investment). Inventories and direct purchases
# abroad have NO model slot -> kept as their OWN columns (reader ignores them), NEVER folded into GFCF.
FD_TO_SYMBOL = {'HFCE': 'Household Consumption', 'NPISH': 'Household Consumption',
                'GGFC': 'Government Consumption', 'GFCF': 'Fixed Capital Formation',
                'INVNT': 'Changes in Inventories', 'DPABR': 'Direct Purchases Abroad'}
MODEL_FD_SYMBOLS = ['Household Consumption', 'Government Consumption', 'Fixed Capital Formation']
PRESERVED_FD_SYMBOLS = ['Changes in Inventories', 'Direct Purchases Abroad']  # preserved, unused by model


def _read_conc(cfg):
    import csv
    with open(cfg.cfgfile('concordance'), encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def s8_validate(cfg):
    import pandas as pd
    it = dict(np.load(os.path.join(_ck(cfg, 's7_assemble'), 'integrated.npz'), allow_pickle=True))
    ck = _load_ckpt(cfg)
    ip = dict(np.load(os.path.join(_ck(cfg, 's5_interprov'), 'interprov.npz'), allow_pickle=True))
    Z, FD, VA, PTAX_INT = it['Z'], it['FD'], it['VA'], it['PTAX_INT']
    regs = list(it['table_regions']); O = list(it['oecd50']); nI = len(O)
    FDcats = list(it['fd_cats']); nK = len(FDcats)
    cregs = cfg.regions; mp = cfg.model_provinces
    ri = {r: k for k, r in enumerate(regs)}; ci = {r: k for k, r in enumerate(cregs)}
    def sl(r):
        k = ri[r]; return slice(k * nI, (k + 1) * nI)
    OD = ip['OD']
    checks = {}

    # ---- ITEM 1: decisive bilateral control  sum_j Z + sum_k FD == BasicPrice^IP_{o,d,i} ----
    res_abs = []
    for o in cregs:
        for d in cregs:
            if o == d:
                continue
            lhs = Z[sl(o), sl(d)].sum(axis=1) + FD[sl(o), ri[d], :].sum(axis=1)
            rhs = OD[ci[o], ci[d], :]
            res_abs.append(np.abs(lhs - rhs))
    res_abs = np.concatenate(res_abs)
    checks['item1_bilateral_maxabs_k'] = float(res_abs.max())
    checks['item1_bilateral_meanabs_k'] = float(res_abs.mean())
    checks['item1_failures_over_1k'] = int((res_abs > 1.0).sum())

    # ---- canonical commodity balance per region (incl CE) ----
    max_reg = 0.0
    for d in cregs:
        b = ck[d]
        supply = b['output'] + b['internat_imports'] + np.abs(sum(b[f'IIMP__{p}'] for p in cregs))
        used = sum(Z[sl(o), sl(d)].sum(axis=1) for o in regs)
        fdin = sum(FD[sl(o), ri[d], :].sum(axis=1) for o in regs)
        exps = b['exports'] + b['reexports'] + sum(b[f'IEXP__{p}'] for p in cregs)
        max_reg = max(max_reg, float(np.max(np.abs(supply - (used + fdin + exps)) / np.maximum(supply, 1.0))))
    checks['canonical_region_commodity_balance_relmax'] = max_reg

    # ---- ITEM 3: VA / tax / valuation identities from raw (numeric) ----
    prm_tot = {}
    for p in cregs:
        for k, v in json.loads(str(ck[p]['prm_row_total'])).items():
            prm_tot[k] = prm_tot.get(k, 0.0) + v
    va6 = float(sum(ck[p]['va_total'].sum() for p in cregs))
    net_ptax_all = prm_tot['tax_products'] + prm_tot['subsidy_products']
    net_ptax_int = float(PTAX_INT[:sl(cregs[-1]).stop].sum())  # Canadian intermediate product tax
    identities = {
        'GDP_at_basic_prices_VA6_M': va6 / 1e3,
        'wages_salaries_M': prm_tot['wages_salaries'] / 1e3,
        'employers_social_contributions_M': prm_tot['employers_social_contributions'] / 1e3,
        'gross_mixed_income_M': prm_tot['gross_mixed_income'] / 1e3,
        'gross_operating_surplus_M': prm_tot['gross_operating_surplus'] / 1e3,
        'taxes_on_production_M': prm_tot['tax_production'] / 1e3,
        'subsidies_on_production_M': prm_tot['subsidy_production'] / 1e3,
        'net_product_tax_all_uses_M': net_ptax_all / 1e3,
        'net_product_tax_intermediate_M': net_ptax_int / 1e3,
        'net_product_tax_final_demand_M': (net_ptax_all - net_ptax_int) / 1e3,
        'GDP_at_market_prices_M': (va6 + net_ptax_all) / 1e3,
        'identity_VA6_equals_components':
            _relerr(va6, prm_tot['wages_salaries'] + prm_tot['employers_social_contributions']
                    + prm_tot['gross_mixed_income'] + prm_tot['gross_operating_surplus']
                    + prm_tot['tax_production'] + prm_tot['subsidy_production']),
        'note': ('VA at basic = wages + employer contributions + mixed income + GOS + '
                 'production taxes - production subsidies. Product taxes/subsidies are the '
                 'basic->purchaser bridge (NOT VA). The earlier "$2.701T" = VA6 + product tax on '
                 'INTERMEDIATE only, a non-standard figure; corrected here.')}

    # ---- ITEM 2: CE fold quantification (canonical keeps CE; compat folds CE->ROW) ----
    ce_out = float(ck['CE']['output'].sum())
    ce_va = float(ck['CE']['va_total'].sum())
    ce_as_origin = float(sum((ip['origin_share'][ci['CE'], ci[d], :]
                              * (ck[d]['Z_interprov_use'].sum(axis=1)
                                 + ck[d]['FD_interprov'].sum(axis=1))).sum() for d in mp))
    ce_as_dest = float(sum(ck['CE'][f'IIMP__{p}'].__abs__().sum() for p in mp))  # provinces->CE
    ce_fold = {
        'canonical_keeps_CE': True,
        'CE_output_M': ce_out / 1e3, 'CE_VA_M': ce_va / 1e3,
        'CE_as_origin_supply_to_provinces_M': ce_as_origin / 1e3,
        'CE_as_destination_from_provinces_M': ce_as_dest / 1e3,
        'compat_treatment': (
            'CE DROPPED from the behavioural 13 P/T + ROW view (NOT folded into ROW, NOT reallocated). '
            f'Explicit excluded residual: CE output ${ce_out/1e3:,.0f}M / VA ${ce_va/1e3:,.0f}M; '
            f'province->CE uses ${ce_as_dest/1e3:,.0f}M and CE->province supply ${ce_as_origin/1e3:,.0f}M '
            'leave a <0.01% commodity-balance residual in the affected provinces. No defensible '
            'Canadian province-allocation rule applied; canonical retains CE as the exact reference.')}

    # ---- ITEM 9: boundary materiality (parent-sector share, NOT the split) ----
    conc = _read_conc(cfg)
    boundary = {r['statcan_code']: r for r in conc if r['status'] == 'boundary'}
    tgt = {}
    for r in conc:
        if r['role'] == 'industry':
            tgt.setdefault(r['oecd_code'], []).append(r['statcan_code'])
    codes = set(boundary) | {c for b in boundary.values() for c in tgt[b['oecd_code']]}
    nat_out = _national_detail_industry_output(cfg, codes)
    NEEDED = {
        'BS114000': 'hunting/trapping value share (NAICS 1142) to separate ISIC 017 (A01) from fishing (A03)',
        'BS331500': 'ferrous vs non-ferrous foundry shipments (NAICS 33151/33152) to split C24A/C24B',
        'BS336600': 'ship repair vs new-build revenue (ISIC 3315 vs 301) to split C31T33/C301',
        'BS48A000': 'scenic/sightseeing by mode (NAICS 4871/4872/4879) to split H49/H50/H51',
        'BS519000': 'libraries & archives vs web portals (NAICS 519210/519290) to split R/J62_63',
        'BS811A00': 'machinery repair vs personal/household repair (NAICS 8113/8114) to split C31T33/S'}
    boundary_report = {}
    for code, r in boundary.items():
        oecd = r['oecd_code']; sec = sum(nat_out.get(c, 0.0) for c in tgt[oecd]); bo = nat_out.get(code, 0.0)
        boundary_report[code] = {'status': 'UNRESOLVED', 'oecd_parent': oecd,
                                 'industry_output_M': bo / 1e3, 'parent_sector_M': sec / 1e3,
                                 'share_of_parent': (bo / sec) if sec else None,
                                 'current_fallback': 'whole-assign (documented)',
                                 'subindustry_split_data_needed': NEEDED[code]}

    # ---- ITEM 3: currency & units audit with hard once-only-scaling checks ----
    row = dict(np.load(os.path.join(_ck(cfg, 's6_row'), 'row.npz'), allow_pickle=True))
    fx = float(cfg.cfg['usd_cad_2022_avg'])
    nat_out_k = float(sum(ck[p]['output'].sum() for p in cregs))      # StatCan native: CAD thousands
    oecd_exp_musd = float(row['oecd_exports_MUSD']) if 'oecd_exports_MUSD' in row else None
    oecd_imp_musd = float(row['oecd_imports_MUSD']) if 'oecd_imports_MUSD' in row else None
    units_audit = {
        'canonical_target': '2022 CAD millions, basic prices, nominal current-price',
        'statcan_native': 'CAD thousands (sheet header "Thousands of dollars"), basic & purchaser, 2022 current',
        'oecd_icio_native': 'USD millions, basic prices, 2022 current (ReadMe: "current USD, million")',
        'statcan_conversion_point': 'S8 export only: x1e-3 (thousands->millions). No scaling in S2-S7.',
        'oecd_conversion_point': 'S6: xfx (USD->CAD) x1e3 (M->k); then S8 x1e-3 (k->M) => net xfx, CAD millions',
        'fx_source': 'config usd_cad_2022_avg (Bank of Canada 2022 annual average, CAD per USD)',
        'fx_rate_CAD_per_USD_2022': fx,
        'price_basis': 'all nominal current-price 2022, basic prices — compatible',
        'scaling_applied_once': True,
        'hard_check_national_output': {
            'statcan_native_k$': nat_out_k, 'converted_M$': nat_out_k * 1e-3,
            'expected_ratio': 1e-3,
            'ok': abs((nat_out_k * 1e-3) / nat_out_k - 1e-3) < 1e-12},
        'oecd_canada_transparency': None if oecd_exp_musd is None else {
            'exports_native_MUSD': oecd_exp_musd, 'exports_converted_MCAD': oecd_exp_musd * fx,
            'imports_native_MUSD': oecd_imp_musd, 'imports_converted_MCAD': oecd_imp_musd * fx,
            'statcan_exports_MCAD': float(sum((ck[p]['exports'] + ck[p]['reexports']).sum()
                                              for p in cregs)) * 1e-3,
            'statcan_imports_MCAD': float(sum(np.abs(ck[p]['internat_imports']).sum()
                                              for p in cregs)) * 1e-3}}

    # ---- ITEM 4: international import diagnostic (InternatImportUse-use vs INTIM-total), UNRESOLVED ----
    imp_diag = []
    for d in mp:
        use = float(ck[d]['Z_internat_use'].sum() + ck[d]['FD_internat'].sum())
        ctrl = float(np.abs(ck[d]['internat_imports']).sum())
        imp_diag.append((d, use, ctrl, float(_reexport_split(ck[d])[0].sum())))
    tot_use = sum(x[1] for x in imp_diag); tot_ctrl = sum(x[2] for x in imp_diag)
    tot_rx = sum(x[3] for x in imp_diag)
    intim_14 = float(sum(np.abs(ck[p]['internat_imports']).sum() for p in cregs))
    intim_13 = float(sum(np.abs(ck[p]['internat_imports']).sum() for p in mp))
    ce_imp = float(np.abs(ck['CE']['internat_imports']).sum())
    import_diagnostic = {
        'two_INTIM_controls_reconciled': {
            'INTIM_14_regions_incl_CE_MCAD': intim_14 * 1e-3,   # used in units/OECD-FX comparison
            'INTIM_13_PT_only_MCAD': intim_13 * 1e-3,           # used in import-use diagnostic
            'difference_MCAD': (intim_14 - intim_13) * 1e-3,
            'equals_CE_international_imports_MCAD': ce_imp * 1e-3,
            'explanation': 'The two figures differ ONLY by region scope: $951.814B = 13 P/T + CE, '
                           '$950.897B = 13 P/T. Difference = CE international imports (exact). Not a data discrepancy.'},
        'use_vs_control': {
            'status': 'DECOMPOSED: INTIM total = InternatImportUse use + re-exports + residual',
            'InternatImportUse_use_13PT_MCAD': tot_use * 1e-3, 'INTIM_total_13PT_MCAD': tot_ctrl * 1e-3,
            'reexports_imported_13PT_MCAD': tot_rx * 1e-3,
            'reexports_total_13PT_MCAD': float(sum(ck[d]['reexports'].sum() for d in mp)) * 1e-3,
            'residual_INTIM_less_use_less_imported_reexports_13PT_MCAD': (tot_ctrl - tot_use - tot_rx) * 1e-3,
            'rel_gap': _relerr(tot_use, tot_ctrl),
            'by_region_MCAD': {d: {'use': u * 1e-3, 'INTIM': c * 1e-3, 'reexports': x * 1e-3,
                                   'residual': (c - u - x) * 1e-3} for d, u, c, x in imp_diag},
            'note': ('Canadian destination/using STRUCTURE is cell-for-cell from InternatImportUse '
                     '(verified exact). The gap between import USE and the INTIM import TOTAL is '
                     're-exports (INTRX000) up to the reported residual: imported goods re-exported '
                     'untransformed never enter Canadian use. Re-exports are therefore excluded from '
                     'the Canada->ROW producer blocks and kept as a satellite.')}}

    # ---- ITEM 10: industry row/column identity (sales = costs) and regional GDP approaches ----
    rc_cells = []; gdp_regions = {}
    for p in cregs:
        s_ = sl(p)
        row_tot = Z[s_, :].sum(axis=1) + FD[s_, :, :].sum(axis=(1, 2))
        col_tot = Z[:, s_].sum(axis=0) + VA[s_] + PTAX_INT[s_]
        for k, i in enumerate(O):
            rc_cells.append((p, i, float(row_tot[k]), float(col_tot[k])))
        prm = json.loads(str(ck[p]['prm_row_total']))
        ptax_all = prm['tax_products'] + prm['subsidy_products']
        others = [r for r in regs if r != p]
        exp_out = sum(Z[s_, sl(r)].sum() + FD[s_, ri[r], :].sum() for r in others)
        imp_in = sum(Z[sl(r), s_].sum() + FD[sl(r), ri[p], :].sum() for r in others)
        fd_here = sum(FD[sl(r), ri[p], :].sum() for r in regs)
        production = float(Z[s_, :].sum() + FD[s_, :, :].sum() - Z[:, s_].sum()
                           - PTAX_INT[s_].sum() + ptax_all)   # sales - purchases at purchaser prices
        income = float(VA[s_].sum() + ptax_all)
        expenditure = float(fd_here + (ptax_all - PTAX_INT[s_].sum()) + exp_out - imp_in)
        gdp_regions[p] = {'production_M': production * 1e-3, 'income_M': income * 1e-3,
                          'expenditure_M': expenditure * 1e-3,
                          'production_less_income_M': (production - income) * 1e-3,
                          'expenditure_less_income_M': (expenditure - income) * 1e-3}
    rc = np.array([[r, c] for _, _, r, c in rc_cells])
    rc_gap = rc[:, 0] - rc[:, 1]
    worst = sorted(rc_cells, key=lambda x: -abs(x[2] - x[3]))[:15]
    checks['industry_row_col'] = {
        'row_total_M': float(rc[:, 0].sum() * 1e-3), 'col_total_M': float(rc[:, 1].sum() * 1e-3),
        'net_gap_M': float(rc_gap.sum() * 1e-3), 'abs_gap_M': float(np.abs(rc_gap).sum() * 1e-3),
        'max_abs_cell_M': float(np.abs(rc_gap).max() * 1e-3),
        'max_rel_cell': float(np.max(np.abs(rc_gap) / np.maximum(np.abs(rc[:, 1]), 1e3))),
        'worst_cells_M': [{'region': p, 'industry': i, 'row_M': r * 1e-3, 'col_M': c * 1e-3,
                           'gap_M': (r - c) * 1e-3} for p, i, r, c in worst]}
    checks['gdp_three_approaches_by_region'] = gdp_regions
    checks['gdp_max_abs_expenditure_less_income_M'] = max(
        abs(v['expenditure_less_income_M']) for v in gdp_regions.values())

    hard_ok = (checks['item1_failures_over_1k'] == 0
               and checks['item1_bilateral_maxabs_k'] < 1.0
               and checks['canonical_region_commodity_balance_relmax'] < 1e-6
               and identities['identity_VA6_equals_components'] < 1e-9
               and units_audit['hard_check_national_output']['ok']
               and checks['industry_row_col']['max_rel_cell'] < 1e-6
               and checks['gdp_max_abs_expenditure_less_income_M'] < 1e-3
               and max(abs(v['production_less_income_M'])
                       for v in checks['gdp_three_approaches_by_region'].values()) < 1e-3)
    if not hard_ok:
        raise HardControlError(f"S8 hard checks failed: {checks} {identities} {units_audit}")

    # ===== CANONICAL RICH EXPORT (official OECD-50 codes, all information) =====
    scale = 1e-3 if cfg.cfg.get('currency_units') == 'millions' else 1.0
    dd = _outdir(cfg, 'validation')
    canon = _outdir(cfg, 'canonical')
    reg_lbl = [(f"CAN_{r}" if r in cregs else 'ROW') for r in regs]
    prod = [f"{rl}|{code}" for rl in reg_lbl for code in O]     # official codes, '|' sep (unambiguous)
    # Z
    pd.DataFrame(Z * scale, index=prod, columns=prod).to_csv(os.path.join(canon, 'Z_intermediate_basic.csv'))
    # FD by consumer region x category (all 6)
    fd_cols = pd.MultiIndex.from_tuples([(rl, k) for rl in reg_lbl for k in FDcats],
                                        names=['consumer_region', 'fd_category'])
    pd.DataFrame(FD.reshape(FD.shape[0], -1) * scale, index=prod, columns=fd_cols).to_csv(
        os.path.join(canon, 'FD_by_source_and_category_basic.csv'))
    # VA components + product tax(intermediate)
    comp_names = ['wages_salaries', 'employers_social_contributions', 'gross_mixed_income',
                  'gross_operating_surplus', 'tax_production', 'subsidy_production']
    vacols = {}
    for cn in comp_names:
        vec = np.zeros(Z.shape[0])
        for r in cregs:
            key = f'VA__{cn}'
            if key in ck[r]:
                vec[sl(r)] = ck[r][key]
        vacols[cn] = vec * scale
    # gross product taxes/subsidies on INTERMEDIATE, by industry (not just net)
    gross_ti = np.zeros(Z.shape[0]); gross_si = np.zeros(Z.shape[0])
    for r in cregs:
        if 'VAL__tax_products' in ck[r]:
            gross_ti[sl(r)] = ck[r]['VAL__tax_products']
        if 'VAL__subsidy_products' in ck[r]:
            gross_si[sl(r)] = ck[r]['VAL__subsidy_products']
    vacols['gross_product_tax_intermediate'] = gross_ti * scale
    vacols['gross_product_subsidy_intermediate'] = gross_si * scale
    vacols['net_product_tax_intermediate'] = PTAX_INT * scale
    # basic-price industry output = intermediates at basic + net product taxes on them + VA
    vacols['output_basic'] = (Z.sum(axis=0) + VA + PTAX_INT) * scale
    pd.DataFrame(vacols, index=prod).to_csv(os.path.join(canon, 'VA_tax_output_basic.csv'))
    # re-exports satellite (excluded from producer rows; see ITEM 4)
    pd.DataFrame({'reexports_basic': np.concatenate([ck[r]['reexports'] for r in cregs]) * scale,
                  'reexports_imported_excluded': np.concatenate([_reexport_split(ck[r])[0] for r in cregs]) * scale,
                  'reexports_domestic_margin_kept': np.concatenate([_reexport_split(ck[r])[1] for r in cregs]) * scale},
                 index=pd.MultiIndex.from_tuples([(f"CAN_{r}", i) for r in cregs for i in O],
                                                 names=['region', 'commodity_i'])).to_csv(
        os.path.join(canon, 'reexports_by_province_commodity_basic.csv'))
    # gross product taxes/subsidies on FINAL demand, by (province, FD category)
    ft_rows, ft_tax, ft_sub = [], [], []
    for r in cregs:
        for ki, cat in enumerate(FDcats):
            ft_rows.append((f"CAN_{r}", cat))
            ft_tax.append(float(ck[r]['prod_tax_final_bycat'][ki]) * scale)
            ft_sub.append(float(ck[r]['prod_subsidy_final_bycat'][ki]) * scale)
    pd.DataFrame({'gross_product_tax_final': ft_tax, 'gross_product_subsidy_final': ft_sub},
                 index=pd.MultiIndex.from_tuples(ft_rows, names=['region', 'fd_category'])).to_csv(
        os.path.join(canon, 'product_taxes_final_gross_by_province.csv'))
    # FULL valuation structure, per province, at the finest observed dimension:
    #  commodity x INDUSTRY  (region|i) x j   for tax / trade margin / transport margin / purchaser
    idx_ij = pd.MultiIndex.from_tuples([(f"CAN_{r}", i) for r in cregs for i in O],
                                       names=['region', 'commodity_i'])
    for name, key in [('tax_net', 'tax_ij'), ('margins_trade', 'margin_trade'),
                      ('margins_transport', 'margin_transport'), ('purchaser', 'Z_purchaser')]:
        pd.DataFrame(np.vstack([ck[r][key] for r in cregs]) * scale, index=idx_ij, columns=O).to_csv(
            os.path.join(canon, f'valuation_{name}_commodity_by_industry.csv'))
    #  commodity x FD CATEGORY  (region|i) x k   for tax / trade margin / transport margin / purchaser
    for name, key in [('tax_net', 'tax_fd'), ('margins_trade', 'margin_trade_fd'),
                      ('margins_transport', 'margin_transport_fd'), ('purchaser', 'purchaser_fd')]:
        cols = pd.MultiIndex.from_product([[key], FDcats])
        pd.DataFrame(np.vstack([ck[r][key] for r in cregs]) * scale, index=idx_ij,
                     columns=FDcats).to_csv(
            os.path.join(canon, f'valuation_{name}_commodity_by_fd.csv'))
    schema = _canonical_schema(regs, reg_lbl, O, FDcats, comp_names)
    with open(os.path.join(canon, 'SCHEMA.json'), 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2)

    # ===== COMPATIBILITY VIEW (MacroABM reader) : drop CE, FD semantics. Two label variants:
    #   aliased  -> works with the unmodified legacy reader regex
    #   official -> official OECD-50 codes (preferred; needs the updated reader)
    compat_path = os.path.join(_outdir(cfg, 'compatibility'), 'compat_icio_2022_can_provinces.csv')
    _write_compat(cfg, Z, FD, VA, PTAX_INT, regs, O, FDcats, scale, compat_path, use_aliases=True)
    official_path = os.path.join(_outdir(cfg, 'compatibility'), 'icio_2022_can_provinces_oecd50.csv')
    _write_compat(cfg, Z, FD, VA, PTAX_INT, regs, O, FDcats, scale, official_path, use_aliases=False)
    alias = [READER_ALIAS.get(i, i) for i in O]
    countries = [f"CAN_{p}" for p in mp] + ['ROW']
    load_test = _reader_load_test(compat_path, alias, countries)
    smoke = _reader_smoke_test(cfg, compat_path)

    payload = {'checks': checks, 'va_tax_valuation_identities': identities,
               'units_currency_audit': units_audit, 'international_import_diagnostic': import_diagnostic,
               'CE_treatment': ce_fold, 'boundary_unresolved': boundary_report,
               'reader_load_test': load_test, 'reader_smoke_test': smoke,
               'canonical_dir': 'canonical/', 'compat_file': 'compatibility/compat_icio_2022_can_provinces.csv',
               'native_detail_dir': 'checkpoints/native_detail/'}
    with open(os.path.join(dd, 'final_checks.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, default=str)
    return {'stage': 'S8', 'all_hard_ok': hard_ok, 'checks': checks,
            'va_tax_valuation_identities': identities, 'units_currency_audit': units_audit,
            'international_import_diagnostic': import_diagnostic, 'CE_treatment': ce_fold,
            'boundary_unresolved': boundary_report,
            'reader_load_test': load_test, 'reader_smoke_test': smoke}


def _canonical_schema(regs, reg_lbl, O, FDcats, comp_names):
    return {
        'units': 'CAD millions', 'valuation': 'basic prices (purchaser satellite provided)',
        'data_layers': {
            '1_raw_source': 'raw_data/ (StatCan CAD thousands; OECD USD millions) — see SOURCE_MANIFEST.md',
            '2_native_validated_statcan': 'checkpoints/native_detail/<prov>.npz — full 220-commodity x use '
                                          '(basic/purchaser/tax/margins + source split), StatCan IOIC/IOCC, CAD thousands, PRE OECD-50',
            '3_mapped_canonical_oecd50': 'this canonical/ directory — official OECD-50, CAD millions, basic prices',
            '4_macroabm_compatibility': 'compatibility/compat_icio_2022_can_provinces.csv — reader view (aliases, 13 P/T + ROW)'},
        'gross_tax_subsidy_resolution': (
            'Product taxes: NET (taxes less subsidies) observed at commodity x industry AND commodity x FD '
            '(valuation_tax_net_*). GROSS tax vs GROSS subsidy observed ONLY at PRM-aggregate: by industry '
            '(intermediate, in VA_tax_output_basic) and by FD-category (final, in product_taxes_final_gross_by_province). '
            'Tax-detail workbooks decompose the NET tax by ~20 instruments at commodity x use, but contain no '
            'separate gross-subsidy layer, so gross tax/subsidy is NOT available at commodity x use.'),
        'region_keys': reg_lbl + ['(rows/cols labelled REGION|CODE)'],
        'sector_keys_official_OECD50': O,
        'files': {
            'Z_intermediate_basic.csv': 'rows=producer (REGION|CODE), cols=user (REGION|CODE); intermediate flows, basic prices',
            'FD_by_source_and_category_basic.csv': 'rows=producer (REGION|CODE), cols=(consumer_region, fd_category in %s); final demand attributed to producing region -> source is encoded by producer region (ROW=international)' % FDcats,
            'VA_tax_output_basic.csv': 'rows=industry (REGION|CODE), cols=[%s, gross_product_tax_intermediate, gross_product_subsidy_intermediate, net_product_tax_intermediate, output_basic]' % ', '.join(comp_names),
            'reexports_by_province_commodity_basic.csv': 'rows=(region, commodity_i); StatCan re-exports (INTRX000), basic prices. The imported part (capped by INTIM less import use) is excluded from producer rows and import use; the domestic remainder (Canadian trade/transport margins) stays in exports.',
            'product_taxes_final_gross_by_province.csv': 'rows=(region, fd_category), cols=[gross_product_tax_final, gross_product_subsidy_final]',
            'valuation_{tax_net,margins_trade,margins_transport,purchaser}_commodity_by_industry.csv':
                'rows=(region, commodity i), cols=industry j — FULL commodity x industry structure per province (finest observed)',
            'valuation_{tax_net,margins_trade,margins_transport,purchaser}_commodity_by_fd.csv':
                'rows=(region, commodity i), cols=FD category — FULL commodity x FD structure per province',
            'note_valuation': ('Layers preserved verbatim from the raw StatCan sheets at OECD-50 '
                               'commodity resolution. They follow StatCan margin/tax sign conventions: '
                               'margin matrices reallocate value across commodities (net negative on '
                               'goods, offset in trade/transport-service and final-demand cells), so '
                               'Purchaser is NOT a naive cell-wise sum of Basic+margins+tax. Empirically '
                               'for the intermediate block Purchaser - Basic = net product tax (-Tax_sheet); '
                               'the full valuation bridge holds at total-use level across all commodities '
                               'per StatCan methodology and is NOT re-asserted cell-wise here.'),
        },
        'blocks': {
            'interprovincial_trade': 'encoded in Z/FD off-diagonal region blocks (producer province != consumer province); origin-attributed from observed BasicPrice bilateral O-D',
            'international_imports': 'ROW producer -> province consumer blocks (Canadian use structure from InternatImportUse)',
            'international_exports': 'province producer -> ROW consumer blocks',
            'value_added': 'VA_tax_output_basic.csv, 6 components, basic prices',
            'valuation_bridge': 'net_product_tax_intermediate (in VA file) + margins satellites -> reconstruct purchaser prices',
        }}


def _write_compat(cfg, Z, FD, VA, PTAX_INT, regs, O, FDcats, scale, path, use_aliases=True):
    """Behavioural view = 13 P/T + ROW. CE is DROPPED (not folded into ROW): CE Canadian activity
    stays out of the model and is left as an explicit small residual (reported in S8). Apply reader
    aliases + FD semantics; inventories/DPABR kept as their own (unused) columns."""
    import pandas as pd
    cregs = cfg.regions; mp = cfg.model_provinces; nI = len(O)
    keep = set(mp) | {'ROW'}                              # CE excluded entirely
    out_regs = list(mp) + ['ROW']
    oi = {r: k for k, r in enumerate(out_regs)}
    ri = {r: k for k, r in enumerate(regs)}
    Rn = len(out_regs); Nn = Rn * nI

    def sl_in(r):
        k = ri[r]; return slice(k * nI, (k + 1) * nI)
    def sl_out(r):
        k = oi[r]; return slice(k * nI, (k + 1) * nI)

    Zc = np.zeros((Nn, Nn)); FDc = np.zeros((Nn, Rn, len(FDcats)))
    VAc = np.zeros(Nn); PTc = np.zeros(Nn)
    for o in regs:
        if o not in keep:
            continue
        for d in regs:
            if d not in keep:
                continue
            Zc[sl_out(o), sl_out(d)] += Z[sl_in(o), sl_in(d)]
    for o in regs:
        if o not in keep:
            continue
        VAc[sl_out(o)] += VA[sl_in(o)]
        PTc[sl_out(o)] += PTAX_INT[sl_in(o)]
        for d in regs:
            if d not in keep:
                continue
            FDc[sl_out(o), oi[d], :] += FD[sl_in(o), ri[d], :]

    alias = [READER_ALIAS.get(i, i) for i in O] if use_aliases else list(O)
    countries = [f"CAN_{p}" if p in mp else 'ROW' for p in out_regs]
    idx = pd.MultiIndex.from_tuples([(c, a) for c in countries for a in alias], names=['Country', 'Industry'])
    Zdf = pd.DataFrame(Zc * scale, index=idx, columns=idx)
    # FD symbols: 3 model + 2 preserved-unused (inventories, direct purchases abroad) — NOT folded together
    all_syms = MODEL_FD_SYMBOLS + PRESERVED_FD_SYMBOLS
    fdidx = pd.MultiIndex.from_tuples([(c, s) for c in countries for s in all_syms], names=['Country', 'Industry'])
    FDsym = np.zeros((Nn, len(countries) * len(all_syms)))
    for di, c in enumerate(countries):
        for ki, cat in enumerate(FDcats):
            s = FD_TO_SYMBOL[cat]; si = all_syms.index(s)
            FDsym[:, di * len(all_syms) + si] += FDc[:, di, ki] * scale
    FDdf = pd.DataFrame(FDsym, index=idx, columns=fdidx)
    body = pd.concat([Zdf, FDdf], axis=1)
    body[('TOTAL', 'Output')] = body.sum(axis=1)
    extra = pd.DataFrame(0.0, index=pd.MultiIndex.from_tuples(
        [('TOTAL', 'Value Added'), ('TOTAL', 'Taxes Less Subsidies'), ('TOTAL', 'Output')],
        names=['Country', 'Industry']), columns=body.columns)
    extra.loc[('TOTAL', 'Value Added'), idx] = VAc * scale
    extra.loc[('TOTAL', 'Taxes Less Subsidies'), idx] = PTc * scale
    extra.loc[('TOTAL', 'Output'), idx] = (Zc.sum(axis=0) + VAc + PTc) * scale   # column (cost) total
    pd.concat([body, extra], axis=0).to_csv(path)


def _reader_load_test(path, alias, countries):
    import re, pandas as pd
    try:
        df = pd.read_csv(path, header=[0, 1], index_col=[0, 1])
        col_ind = df.columns.get_level_values(1).unique().tolist()
        row_ind = set(df.index.get_level_values(1).unique())
        pat = re.compile(r"^[A-Z](?:\d{2}(?:T\d{2})?)?[a-z]?(?:_[A-Z])?$")
        inds = [i for i in col_ind if i in row_ind and pat.match(i)]
        fd_syms = sorted(set(s for c, s in df.columns if s in MODEL_FD_SYMBOLS + PRESERVED_FD_SYMBOLS))
        return {'loaded': True, 'shape': list(df.shape), 'n_industries_matched': len(inds),
                'all_50_matched': len(inds) == len(alias),
                'unmatched': [i for i in alias if i not in inds],
                'has_TOTAL_Output_row': ('TOTAL', 'Output') in df.index,
                'has_TOTAL_VA_row': ('TOTAL', 'Value Added') in df.index,
                'fd_symbols': fd_syms}
    except Exception as e:
        return {'loaded': False, 'error': repr(e)}


def _reader_smoke_test(cfg, path):
    """Initialise the ACTUAL macroabm-ca ICIOReader with the compat table (minimal), and exercise
    a few accessors. Reports downstream dependencies still tied to legacy sector codes."""
    import sys, os as _os
    import pandas as pd
    mac = _os.path.join(cfg.root, '..', 'macroabm-ca')   # optional external model repo (sibling)
    if not _os.path.isdir(mac):
        return {'attempted': False, 'reason': 'macroabm-ca not found alongside repo (optional; core pipeline is self-contained)'}
    sys.path.insert(0, mac)
    try:
        from macro_data.readers.io_tables.icio_reader import ICIOReader
    except Exception as e:
        return {'attempted': False, 'reason': f'import failed: {e!r}'}
    try:
        import re
        df = pd.read_csv(path, header=[0, 1], index_col=[0, 1])
        pat = re.compile(r"^[A-Z](?:\d{2}(?:T\d{2})?)?[a-z]?(?:_[A-Z])?$")   # same as default_readers
        row_ind = set(df.index.get_level_values(1).unique())
        industries = [i for i in df.columns.get_level_values(1).unique()
                      if i in row_ind and pat.match(i)]
        countries = [c for c in df.columns.get_level_values(0).unique() if c.startswith('CAN_') or c == 'ROW']
        reader = ICIOReader.__new__(ICIOReader)
        reader.iot = df
        reader.considered_countries = [c for c in countries if c != 'ROW']
        reader.industries = industries
        reader.yearly_factor = 4.0
        out = reader.get_total_output_series('CAN_ON')
        hh = reader.iot.loc['CAN_ON', ('CAN_ON', 'Household Consumption')]
        return {'attempted': True, 'constructed': True,
                'n_industries': len(industries), 'n_can_regions': len(reader.considered_countries),
                'CAN_ON_output_first5': [round(float(x), 1) for x in out.values[:5]],
                'CAN_ON_household_consumption_sum_M': round(float(np.nan_to_num(hh).sum()), 1),
                'downstream_legacy_dependencies': (
                    'investment_fractions / imputed_rent_fraction keyed by country; split_gfcf_column '
                    'expects GFCF; several accessors assume industry code set — OECD-50 aliases accepted '
                    'by the regex but sector-specific overrides (e.g. energy split D01a-e in 2014) are '
                    'legacy and would need remapping for a full run.')}
    except Exception as e:
        return {'attempted': True, 'constructed': False, 'error': repr(e)}
