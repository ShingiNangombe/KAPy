"""
#Setup for debugging with VS code 
import os
print(os.getcwd())
import helpers
os.chdir("..")
import KAPy
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
ensID=list(wf['ensstats'].keys())[0]
inFile=wf['ensstats'][ensID]
%matplotlib inline
"""

import xarray as xr
import pandas as pd
import geopandas as gpd
import regionmask
import numpy as np
import os
from cdo import Cdo
from . import helpers

def generateArealstats(config, inFile, outFile):
    # Generate statistics over an area by applying a polygon mask and averaging
    # Setup xarray
    # Note that we need to use open_dataset here, as the ensemble files have
    # multiple data variables in them
    thisDat = xr.open_dataset(inFile[0],
                              use_cftime=True)

    #Identify the time / period coordinate first
    if 'time' in thisDat.dims:
        tCoord='time'
    elif 'periodID' in thisDat.dims:
        tCoord='periodID'
    else:
        raise ValueError(f'Cannot find time or periodID coordinate in "{inFile[0]}".')

    # If using area weighting, get the pixel size
    if config['arealstats']['useAreaWeighting']:
        cdo=Cdo()
        pxlSize=cdo.gridarea(input=thisDat[{tCoord:0,"seasonID":0}].indicator,
                             returnXArray='cell_area')
    else:
        pxlSize=thisDat[{tCoord:0,"seasonID":0}].indicator
        pxlSize.values[:]=1

    # If we have a shapefile defined, then work with it
    if config['arealstats']['shapefile']!='':
        #Import shapefile
        shapefile = gpd.GeoDataFrame.from_file(config['arealstats']['shapefile'])

        #Setup mask
        maskRegions=regionmask.from_geopandas(shapefile,
                                       names=config['arealstats']['idColumn'],
                                       abbrevs=config['arealstats']['idColumn'],
                                       name='test')
        maskRaster=maskRegions.mask_3D_frac_approx(thisDat)

        #Apply masking and weighting and calculate
        wtThis=maskRaster*pxlSize
        statDims=set(thisDat.dims) - set(['region','periodID','time',"seasonID",'percentiles'])
        wtMean = thisDat.weighted(wtThis).mean(dim=statDims)
        wtMean.name='mean'
        wtSd = thisDat.weighted(wtThis).std(dim=statDims)
        wtSd.name='sd'

        #Output object
        dfOut=xr.merge([wtMean,wtSd]).to_dataframe()
        dfOut=dfOut.rename(columns={'names':'area'})
        dfOut=dfOut.drop(columns=['abbrevs'])

    #Otherwise, just average spatially
    else:
        # Average spatially over the time dimension
        spDims =set(thisDat.dims)-set(['time','periodID',"seasonID",'percentiles'])
        spMean = thisDat.weighted(pxlSize).mean(dim=spDims)
        spMeanDf=spMean.to_dataframe()
        spMeanDf['statistic']='mean'
        spSd = thisDat.weighted(pxlSize).std(dim=spDims)
        spSdDf=spSd.to_dataframe()
        spSdDf['statistic']='sd'

        # Save files pandas
        dfOut = pd.concat([spMeanDf,spSdDf])
        dfOut["area"] = "all"  

    #Write out date without time for easier handling
    dfOut=dfOut.reset_index()
    if 'time' in dfOut.columns:
        dfOut['time']=[d.strftime("%Y-%m-%d") for d in dfOut['time']]
    
    #Write results out
    dfOut.to_csv(outFile[0],index=False)



"""
inFiles=wf['arealstats'].keys()
outFile=["results/5.areal_statistics/Areal_statistics.csv"]
"""

def combineArealstats(config, inFiles, outFile):
    #Load individual files
    dat = []
    for f in inFiles:
        datIn=pd.read_csv(f)
        datIn.insert(0,'sourcePath',f)
        datIn.insert(0,'filename',os.path.basename(f))
        dat += [datIn]
    datdf = pd.concat(dat)
    
    #Split out the defined elements
    datdf.insert(2,'memberID',datdf['filename'].str.extract("^[^_]+_[^_]+_[^_]+_[^_]+_(.*).csv$"))
    datdf.insert(2,'expt',datdf['filename'].str.extract("^[^_]+_[^_]+_[^_]+_([^_]+)_.*$"))
    datdf.insert(2,'gridID',datdf['filename'].str.extract("^[^_]+_[^_]+_([^_]+)_.*$"))
    datdf.insert(2,'srcID',datdf['filename'].str.extract("^[^_]+_([^_]+)_.*$"))
    datdf.insert(2,'indID',datdf['filename'].str.extract("^([^_]+)_.*$"))

    #Drop the filename and write out
    datdf.drop(columns=['filename','sourcePath']).to_csv(outFile[0],index=False)

