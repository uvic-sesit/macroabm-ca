"""Standalone scientific diagnostic figure from the measured CSVs."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent/'outputs/BE'


def main():
    q=pd.read_csv(OUT/'quarterly.csv')
    fig,axes=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
    for arm,style in [('iv-ACDpAIFB','-'),('iv-ACDpAIFBP','--')]:
        for seed in range(3):
            x=q[(q.arm==arm)&(q.variant=='base')&(q.seed==seed)]
            for ax,column,scale in zip(axes,['consumption','cash_saving_pct','constrained_pct'],[1e9,1,1]):
                ax.plot(x.quarter,x[column]/scale,style,label=f'{"B" if arm.endswith("B") else "B+payout"}, seed {seed}',color=f'C{seed}')
    axes[0].axhline(377.8455,color='black',lw=.8,label='2022 quarterly C target')
    axes[1].axhspan(-5.6,4.4,color='grey',alpha=.18)
    axes[1].axhline(-.6,color='black',lw=.8)
    axes[2].set_ylim(0,1)
    for ax,title,unit in zip(axes,['Consumption','Cash saving','D-constrained households'],['CAD B / quarter','% of cash DI','% of households']):
        ax.set(title=title,xlabel='Quarter',ylabel=unit,xticks=[1,4,8,12]);ax.grid(alpha=.2)
    axes[0].legend(fontsize=6)
    fig.savefig(OUT/'buffer_gate_paths.png',dpi=180)
    fig.savefig(OUT/'buffer_gate_paths.pdf')


if __name__=='__main__':main()
