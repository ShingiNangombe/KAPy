# Plotting functions to be used in notebooks
"""
#Debugging setup for VS Code
import os
print(os.getcwd())
os.chdir("..")
import KAPy
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
"""

from plotnine import *
import pandas as pd
import os
import xarray as xr
import matplotlib
from datetime import datetime

# Set default backend to workaround problems caused by the
# default not being uniform across systems - in particular, we 
# hit a problem with micromamba vs conda having different defaults.
# This lead to a crashes when running in a non-Gui environment
matplotlib.use('Agg')

# Boxplot---------------------------------------------------------------------------
"""
indID='101'
outFile='outputs/7.plots/101_boxplot.png'
srcFiles=wf['plots'][outFile]
"""

def makeBoxplot(config, indID, srcFiles, outFile=None):
    # Extract indicator info
    thisInd = config["indicators"][indID]

    # Load csv files as panadas dataframes
    # Note that we need to make sure that we read the ID's as strings
    dat = []
    for f in srcFiles:
        datIn = pd.read_csv(f)
        datIn["fname"] = os.path.basename(f)
        datIn["periodID"] = [str(x) for x in datIn["periodID"]]
        datIn["source"] = datIn["fname"].str.extract("^[^_]+_([^_]+)_[^_]+_[^_]+_.*$")
        datIn["experiment"] = datIn["fname"].str.extract("^[^_]+_[^_]+_[^_]+_([^_]+)_.*$")
        dat += [datIn]
    datdf = pd.concat(dat)
    datdf['lbl']=[ rw['source'] + "-" + rw['experiment'] if rw['experiment']!='no-expt' else rw['source']
                  for idx,rw in datdf.iterrows()]


    # Get metadata from configuration
    ptileTbl = (
        pd.DataFrame.from_dict(
            config["ensembles"], orient="index", columns=["percentiles"]
        )
        .reset_index()
        .rename(columns={"index": "ptileLbl"})
    )
    periodTbl = pd.DataFrame.from_dict(config["periods"], orient="index")
    periodLblDict = {
        x["id"]: f"{x['name']}\n({x['start']}-{x['end']})"
        for i, x in periodTbl.iterrows()
    }

    # Now merge into dataframe and pivot for plotting
    pltLong = pd.merge(datdf, ptileTbl, on="percentiles", how="left")
    pltDatWide = pltLong.pivot_table(
        index=["lbl", "periodID","seasonID","statistic"], columns="ptileLbl", values="indicator"
    ).reset_index()

    # Filter remaining data
    pltDat=pltDatWide[pltDatWide['statistic']=='mean']

    # Now plot
    p = (
        ggplot(pltDat)
        + facet_wrap("~seasonID")
        + geom_boxplot(
            mapping=aes(
                x="periodID",
                fill="lbl",
                middle="centralPercentile",
                ymin="lowerPercentile",
                ymax="upperPercentile",
                lower="lowerPercentile",
                upper="upperPercentile",
            ),
            width=0.5,
            stat="identity",
        )
        + labs(
            x="Period",
            y=f"Value ({thisInd['units']})",
            title=f"{thisInd['name']} ",
            fill="",
        )
        + scale_x_discrete(labels=periodLblDict,    )
        + theme_bw()
        + theme(legend_position="bottom",
                 panel_grid_major_x=element_blank(),
                 axis_text_x=element_text(angle=90, hjust=0.5))                 
    )

    # Output
    if outFile is not None:
        p.save(outFile[0],
               verbose=False)
    return p


# Spatialplot -----------------------------------------------------------
"""
indID='101'
outFile='outputs/7.plots/101_spatial.png'
srcFiles=wf['plots'][outFile]
"""
def makeSpatialplot(config, indID, srcFiles, outFile=None):
    # Extract indicator info
    thisInd = config["indicators"][indID]

    # Read netcdf files using xarray and calculate difference
    datdf = []
    for d in srcFiles:
        # Import object
        thisdat = xr.open_dataset(d)
        # We want to plot a spatial map of the first and last indicators
        # We take the first season
        firstlast = thisdat.isel(periodID=[0,-1],seasonID=0)
        firstlastdf = firstlast.indicator_mean.to_dataframe().reset_index()
        firstlastdf["fname"] = os.path.basename(d)
        firstlastdf["source"] = firstlastdf["fname"].str.extract("^[^_]+_([^_]+)_[^_]+_[^_]+_.*$")
        firstlastdf["experiment"] = firstlastdf["fname"].str.extract("^[^_]+_[^_]+_[^_]+_([^_]+)_.*$")
        datdf += [firstlastdf]
    pltDat = pd.concat(datdf)
    pltDat['lbl']=[ rw['source'] + "-" + rw['experiment'] if rw['experiment']!='no-expt' else rw['source']
                  for idx,rw in pltDat.iterrows()]

    #Setup period labelling
    periodTbl = pd.DataFrame.from_dict(config["periods"], orient="index")
    periodLblDict = {
        x["id"]: f"{x['name']}\n({x['start']}-{x['end']})"
        for i, x in periodTbl.iterrows()
    }
    pltDat['periodLbl']= [ periodLblDict[p] for p in pltDat['periodID']]

    #Identify spatial coordinates
    spDimX=[d for d in pltDat.columns if d in ['x','longitude','long','lon','eastings']]
    spDimY=[d for d in pltDat.columns if d in ['y','latitude','lat','northings']]
    if len(spDimX)==0:
        raise ValueError("Cannot identify x-spatial coordinate.")
    if len(spDimY)==0:
        raise ValueError("Cannot identify y-spatial coordinate.")
    pltDat['x']=pltDat[spDimX]
    pltDat['y']=pltDat[spDimY]

    # Make plot
    p = (
        ggplot(pltDat, aes(x="x", y="y", fill="indicator_mean"))
        + geom_raster()
        + facet_grid("periodLbl~lbl")
        + theme_bw()
        + labs(
            x="",
            y="",
            fill=f"Value\n({thisInd['units']})",
            title=f"{thisInd['name']} "
        )
        + scale_x_continuous(expand=[0, 0])
        + scale_y_continuous(expand=[0, 0])
        + theme(legend_position="bottom",
                axis_text_x=element_blank(),
                axis_text_y=element_blank(),
                axis_ticks_major_x=element_blank(),
                axis_ticks_major_y=element_blank())
        + coord_fixed()
    )

    # Output
    if outFile is not None:
        p.save(outFile[0],
               verbose=False)
    return p


# Lineplot------------------------------------------------------------------
"""
indID='101y'
outFile=f'outputs/7.plots/{indID}_lineplot.png'
srcFiles=wf['plots'][outFile]
"""


def makeLineplot(config, indID, srcFiles, outFile=None):
    # Extract indicator info
    thisInd = config["indicators"][indID]

    # Load csv files as panadas dataframes
    dat = []
    for f in srcFiles:
        datIn = pd.read_csv(f)
        datIn["fname"] = os.path.basename(f)
        datIn["source"] = datIn["fname"].str.extract("^[^_]+_([^_]+)_[^_]+_[^_]+_.*$")
        datIn["experiment"] = datIn["fname"].str.extract("^[^_]+_[^_]+_[^_]+_([^_]+)_.*$")
        dat += [datIn]
    datdf = pd.concat(dat)
    #Use datetime library to handle dates longer than 2262 and plotting in plotnine
    datdf["datetime"] = [datetime.strptime(d,"%Y-%m-%d") for d in datdf["time"]]
    datdf['lbl']=[ rw['source'] + "-" + rw['experiment'] if rw['experiment']!='no-expt' else rw['source']
                  for idx,rw in datdf.iterrows()]

    # Now select data for plotting
    # We only plot the central value, not the full range
    # Drop the standard deviation - we only want the mean
    pltDat = datdf[datdf["percentiles"] == config["ensembles"]["centralPercentile"]]
    pltDat = pltDat[pltDat["statistic"] == "mean"]

    # Now plot
    p = (
        ggplot(pltDat, aes(x="datetime", y="indicator", colour="lbl"))
        + facet_wrap("~seasonID",as_table=False,dir="v")
        + geom_point()
        + labs(
            x="",
            y=f"Value ({thisInd['units']})",
            title=f"{thisInd['name']} ",
            colour="",
        )
        + theme_bw()
        + scale_x_datetime(date_labels="%Y")
        + theme(legend_position="bottom")
    )
    # Output
    if outFile is not None:
        p.save(outFile[0],
               verbose=False)
    return p
