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
from cdo import Cdo

def generateArealstats(outFile, inFile, tempDir,useAreaWeighting,shapefile,idColumn):
    # Generate statistics over an area by applying a polygon mask and averaging
    # Setup xarray
    # Note that we need to use open_dataset here, as the ensemble files have
    # multiple data variables in them
    time_coder=xr.coders.CFDatetimeCoder(use_cftime=True)
    thisDat = xr.open_dataset(inFile[0],
                              decode_times=time_coder)

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
    if useAreaWeighting:
        cdo=Cdo(tempdir=tempDir)
        pxlSize=cdo.gridarea(input=spGrid,returnXArray='cell_area')
    else:
        pxlSize=spGrid
        pxlSize.values[:]=1
        pxlSize.name="cell_area"

    # If we have a shapefile defined, then work with it
    if shapefile!='':
        #Import shapefile and drop CRS
        shapefile = gpd.read_file(shapefile)
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
            thisOut.insert(0,'areaID',thisArea[idColumn] )
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
        dfOut.insert(0,'areaID',"all" )

    #Write out date without time for easier handling
    dfOut=dfOut.reset_index()
    if 'time' in dfOut.columns:
        dfOut['time']=[d.strftime("%Y-%m-%d") for d in dfOut['time']]
    
    #Write results out
    dfOut.to_csv(outFile[0],index=False)



