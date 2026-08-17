import random

import numpy as np
import pandas as pd


def _largest_remainder(weights: np.ndarray, total: int) -> np.ndarray:
    """Integer allocation of ``total`` across bins proportional to ``weights`` (need not sum to 1),
    using the largest-remainder method so the result sums exactly to ``total``.
    """
    if total <= 0 or weights.sum() <= 0:
        return np.zeros(len(weights), dtype=int)
    raw = weights / weights.sum() * total
    counts = np.floor(raw).astype(int)
    shortfall = int(total - counts.sum())
    if shortfall > 0:
        order = np.argsort(-(raw - counts))  # largest fractional remainder first
        counts[order[:shortfall]] += 1
    return counts


def reallocate_employment_by_shares(
    individual_data: pd.DataFrame,
    target_shares: np.ndarray,
    n_industries: int,
    min_workers: int = 1,
) -> pd.DataFrame:
    """Reassign employed individuals' ``Employment Industry`` to match target sector shares.

    Used to wire the validated StatCan 36-10-0489 province x OECD-50 employment structure onto a
    synthetic population whose employment distribution otherwise comes from the HFCS (aggregate,
    France-proxy) allocation split by output shares. Only the sector label of already-employed
    individuals changes -- activity status, income, and household links are preserved, so
    household/labour-force accounting is untouched. The sector wage bill (set firm-side from SEA
    Labour Compensation) is independent of headcount, so this corrects wage/worker and labour
    productivity without touching value added.

    Target counts give every sector at least ``min_workers`` (mirroring
    ``ensure_minimum_workers_in_industries``): the model builds one firm per sector and needs each
    staffed, and StatCan reports exact-zero employment for some (province, sector) cells. The
    remaining workers are distributed across sectors proportional to ``target_shares`` via the
    largest-remainder method, so the counts sum exactly to the employed total.

    Args:
        individual_data: population individuals; needs integer-coded ``Employment Industry`` (0..n-1)
            and ``Activity Status`` (1 == employed).
        target_shares: length-``n_industries`` shares (aligned to the model industry order).
        n_industries: number of sectors.
        min_workers: floor of employed persons per sector.

    Returns:
        The same DataFrame with reallocated ``Employment Industry`` for employed individuals.
    """
    employed_positions = np.flatnonzero((individual_data["Activity Status"] == 1).to_numpy())
    n_employed = len(employed_positions)
    floor_total = n_industries * min_workers
    if n_employed < floor_total:
        # Not enough employed persons to staff every sector at the floor; leave the existing
        # allocation (ensure_minimum_workers_in_industries already guaranteed >=1 per sector).
        return individual_data

    shares = np.asarray(target_shares, dtype=float).copy()
    shares[~np.isfinite(shares)] = 0.0
    counts = np.full(n_industries, min_workers, dtype=int)
    counts += _largest_remainder(shares, n_employed - floor_total)
    assert counts.sum() == n_employed and counts.min() >= min_workers

    shuffled = employed_positions.copy()
    np.random.shuffle(shuffled)
    labels = individual_data.index[shuffled]
    start = 0
    for industry in range(n_industries):
        end = start + counts[industry]
        individual_data.loc[labels[start:end], "Employment Industry"] = industry
        start = end
    return individual_data


def ensure_minimum_workers_in_industries(individual_data: pd.DataFrame, n_industries: int) -> pd.DataFrame:
    """
    Ensures that each industry has at least one employed individual (Activity Status == 1).
    If any industry has zero workers:
      1) Attempt to reassign surplus employed individuals from other industries.
      2) If not enough employed, convert some unemployed individuals (Activity Status == 2).
      3) If not enough total individuals, raise ValueError.

    Args:
        individual_data (pd.DataFrame): DataFrame of individuals.
          Must contain columns "Activity Status" (1=employed, 2=unemployed)
          and "Employment Industry" (integer-coded from 0..n_industries-1).
        n_industries (int): Number of distinct industries.

    Returns:
        pd.DataFrame: Updated individual_data, with possible changes to
                      "Activity Status" and "Employment Industry".
    """

    # Helper to count how many workers are employed in each industry
    def count_employees(data: pd.DataFrame) -> np.ndarray:
        counts = np.zeros(n_industries, dtype=int)
        for ind in range(n_industries):
            counts[ind] = np.sum((data["Employment Industry"] == ind) & (data["Activity Status"] == 1))
        return counts

    employees_per_industry = count_employees(individual_data)
    zero_employee_industries = np.where(employees_per_industry == 0)[0]

    # If every industry has at least one employee, do nothing
    if len(zero_employee_industries) == 0:
        return individual_data

    # Otherwise, we need to fill those empty industries
    total_employed = employees_per_industry.sum()

    # Check if total employed >= number of industries
    if total_employed >= len(zero_employee_industries):
        # Reassign surplus employees from industries with many workers
        # until no industry is empty
        for industry_idx in zero_employee_industries:
            # find an industry with surplus = employees_per_industry[i] > 1
            surplus_inds = np.where(employees_per_industry > 1)[0]
            if len(surplus_inds) == 0:
                break  # no more surplus to take from

            # pick the industry with the greatest surplus
            donor_ind = surplus_inds[np.argmax(employees_per_industry[surplus_inds])]
            # find one person in that donor industry
            donor_candidates = individual_data[
                (individual_data["Employment Industry"] == donor_ind) & (individual_data["Activity Status"] == 1)
            ].index.tolist()

            if len(donor_candidates) == 0:
                # This shouldn't happen if employees_per_industry was correct, but just in case
                continue

            # pick any one of them (could do random or other logic)
            chosen_one = random.choice(donor_candidates)
            # reassign this person
            individual_data.at[chosen_one, "Employment Industry"] = industry_idx
            # employees remain employed
            # update counters
            employees_per_industry[donor_ind] -= 1
            employees_per_industry[industry_idx] += 1

        # re-check if we still have empty industries
        employees_per_industry = count_employees(individual_data)
        zero_employee_industries = np.where(employees_per_industry == 0)[0]

    # If some industries are still zero, try using unemployed
    if len(zero_employee_industries) > 0:
        total_unemployed = np.sum(individual_data["Activity Status"] == 2)
        if total_employed + total_unemployed >= len(zero_employee_industries):
            # We'll convert some unemployed
            # gather unemployed indices
            unemployed_indices = individual_data[(individual_data["Activity Status"] == 2)].index.tolist()

            # fill empty industries from unemployed pool
            for industry_idx in zero_employee_industries:
                if len(unemployed_indices) == 0:
                    break
                # pick any unemployed person
                chosen_one = random.choice(unemployed_indices)
                unemployed_indices.remove(chosen_one)
                # make them employed in the empty industry
                individual_data.at[chosen_one, "Activity Status"] = 1
                individual_data.at[chosen_one, "Employment Industry"] = industry_idx

            # recalc employees again
            employees_per_industry = count_employees(individual_data)
            zero_employee_industries = np.where(employees_per_industry == 0)[0]

    # Final check — if we still have empty industries, raise an error
    if len(zero_employee_industries) > 0:
        raise ValueError(
            "Not enough individuals to fill each industry with at least one worker. "
            "Consider increasing the scale of the simulation."
        )

    return individual_data
