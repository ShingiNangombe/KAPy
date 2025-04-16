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
asID=list(wf['arealstats'].keys())[0]
inFile=wf['arealstats'][asID]
%matplotlib inline
"""

import xarray as xr
import pandas as pd
import geopandas as gpd
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
    
    #Identify coordinate types. Some logic is required here, as the coordinates
    #presented can vary based on time_binning and whether it is an ensemble stat or member
    spDims =list(set(thisDat.dims)-set(['time','periodID',"seasonID",'percentiles']))
    nonspDims=list(set(thisDat.dims)-set(spDims))
    spGrid=thisDat.isel({k : 0 for k in nonspDims},drop=True)[list(thisDat.data_vars)[0]]

    # If using area weighting, get the pixel size
    if config['arealstats']['useAreaWeighting']:
        cdo=Cdo(tempdir=config['dirs']['tempDir'])
        pxlSize=cdo.gridarea(input=spGrid,returnXArray='cell_area')
    else:
        pxlSize=spGrid
        pxlSize.values[:]=1
        pxlSize.name="cell_area"

    # If we have a shapefile defined, then work with it
    if config['arealstats']['shapefile']!='':
        #Import shapefile and drop CRS
        shapefile = gpd.read_file(config['arealstats']['shapefile'])
        shapefile.crs=None

        #Use geopandas as the base for this computation. We use the 
        #pxlSize as the basis for this
        pxlDf = pxlSize.to_dataframe().reset_index()
        pxlGdf = gpd.GeoDataFrame(pxlDf.cell_area,
                               geometry=gpd.points_from_xy(pxlDf[spDims[1]],pxlDf[spDims[0]]))

        #Loop over polygons
        outList=[]
        for thisIdx, thisArea in shapefile.iterrows():
            #Which points are in the polygon? Setup a mask
            pxlDf['inPoly'] = pxlGdf.within(thisArea.geometry)
            pxlMask=pxlDf.set_index(spDims).to_xarray()
            pxlWts=pxlMask.inPoly*pxlSize
            
            #Apply masking and weighting and calculate
            wtMeanDf = thisDat.weighted(pxlWts).mean(dim=spDims).to_dataframe().reset_index()
            wtMeanDf['arealStatistic']='mean'
            wtSdDf = thisDat.weighted(pxlWts).std(dim=spDims).to_dataframe().reset_index()
            wtSdDf['arealStatistic']='sd'

            #Output object
            thisOut=pd.concat([wtMeanDf,wtSdDf])
            thisOut['areaID'] =thisArea[config['arealstats']['idColumn']] 
            outList += [thisOut]
        dfOut=pd.concat(outList)

    #Otherwise, just average spatially
    else:
        # Average spatially over the time dimension
        spMean = thisDat.weighted(pxlSize).mean(dim=spDims)
        spMeanDf=spMean.to_dataframe()
        spMeanDf['arealStatistic']='mean'
        spSd = thisDat.weighted(pxlSize).std(dim=spDims)
        spSdDf=spSd.to_dataframe()
        spSdDf['arealStatistic']='sd'

        # Save files pandas
        dfOut = pd.concat([spMeanDf,spSdDf])
        dfOut["areaID"] = "all"  

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
    datdf.insert(2,'datasetID',datdf['filename'].str.extract("^[^_]+_([^_]+)_.*$"))
    datdf.insert(2,'indID',datdf['filename'].str.extract("^([^_]+)_.*$"))

    #Drop the filename and write out
    datdf.drop(columns=['filename','sourcePath']).to_csv(outFile[0],index=False)

