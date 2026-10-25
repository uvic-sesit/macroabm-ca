"""Two-quarter SG accounting gate, independent of the failed cost gate."""
import sys,argparse
import ih_diagnostics as ih
from build_sg import target
from prepare_sg import OUT,sha
def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['FS','FS_T'],required=True);a=p.parse_args()
    ih.qe.PICKLE=target(a.arm);ih.qe.PICKLE_SHA256=sha(target(a.arm))
    sys.argv=[sys.argv[0],'--arm','F_CFC','--variant','SG_'+a.arm,'--quarters','2','--seed','0','--output',str(OUT/'runs')];ih.main()
if __name__=='__main__':main()
