"""
#Setup for debugging with VS code
import os
print(os.getcwd())
os.chdir("KAPy/workflow")
import KAPy
import KAPy.helpers as helpers
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
thisCal='tas-ba'
outFile=list(wf['calibratedVars'][thisCal])[0]
histsimFile=wf['calibratedVars'][thisCal][outFile]['histsim']
refFile=wf['calibratedVars'][thisCal][outFile]['ref']
import matplotlib.pyplot as plt
%matplotlib inline
"""

import xarray as xr
import tempfile
import xesmf as xe
import json
from . import helpers
#from dask.distributed import Client

def calibrate(config,histsimFile,refFile,outFile, thisCal):
    # We choose to follow here the Xclim typology of ref / hist / sim, with the
    # assumption that the hist and sim part are contained in the same file ("histsim)")
    # The general strategy employed is as follows:
    # * Regrid histsim onto the reference grid
    # * Merge histsim and ref into one dataset object. This requires a degree of
    #   massaging of the time units to make sure everything is comparable
    # * Apply the bias-correction function to chunks of the combined dataset using dask

    #Setup ------------------------
    calCfg=config['calibration'][thisCal]
    histsim=helpers.readFile(histsimFile)
    refds=helpers.readFile(refFile,chunks={'time':-1})
 #   client=Client()
  #  print(client.dashboard_link)
    
    # Regrid to common spatial grids ------------------
    # Regrid histsim using nearest neighbour interpolation to the refFile grid. 
    # We have tried several iterations of this based on CDO, but CDO unfortunately doesn't
    # respect the chunking of the histsim file. xESMF is currently our tool of choice
    # due to its ability to work ok with dask.
    # Start by getting the regridding weights
    regrdWtsFname=tempfile.NamedTemporaryFile(dir=config['dirs']['tempDir'],
                                                delete=False,
                                                prefix="regrdWts_",
                                                suffix=".nc").name
    regrdr=xe.Regridder(histsim,refds,
                       method="nearest_s2d",
                       filename=regrdWtsFname)
    # Then apply the regridding. 
    # The regridder seems to work best when it can work with all of the spatial elements 
    # together, implying full spatial chunking. But this creates problems with the later
    # steps of the calibration, which require that we have the full timeseries in memory.
    # We therefore choose to write the regridding data to disk at this point with a 
    # chunking pattern that is amenable to further work downstrem. 
    rechunkSpace={d: -1 for d in histsim.dims if d!='time'}
    histsimRechunked=histsim.chunk(rechunkSpace)
    regrdFname=tempfile.NamedTemporaryFile(dir=config['dirs']['tempDir'],
                                                delete=False,
                                                prefix="histsimNN_",
                                                suffix=".nc").name
    histsimNN=regrdr(histsimRechunked,output_chunks=(-1,-1),keep_attrs=True)
    chunkThisWay=[min([256,16,16][i],histsimNN.shape[i]) for i in range(0,3)]
    histsimNN.to_netcdf(regrdFname,
              encoding={histsimNN.name:{'chunksizes':chunkThisWay}})

    #Now reopen histsimNN with a time-oriented chunking
    histsimNN=helpers.readFile(regrdFname,chunks={'time':-1}).unify_chunks()

    # Prepare combined dataset ------------------------------
    # From a bias-correction perspective, the only part of the reference dataset that
    # is interesting is the common period data - there could be a whole lot more
    # that we otherwise don't use. We therefore drop the uninteresting parts
    refdsCP=helpers.timeslice(refds,
                     calCfg['calPeriodStart'],
                     calCfg['calPeriodEnd'])
    # Merge into one dataset object, with common spatial dimensions but
    # differentiated time dimensions. Note the need to unify the chunking
    refdsCPtime=refdsCP.rename({"time": "reftime"})
    combDS2=xr.Dataset({'histsim':histsimNN.unify_chunks(),
                        'ref':refdsCPtime.unify_chunks()})
    combDS=combDS2.unify_chunks()

    #Parallelised calibration functions ------------------------------
    def calibrateThisChunk(chnk,calCfg):
        #Debug
        # hs=combDS.histsim.data.blocks[0,0,0].compute()
        # rf=combDS.ref.data.blocks[0,0,0].compute()
        #Extract the data from the input block
        hs=chnk.histsim
        rfCP=chnk.ref

        #Truncate time slice to the common calibration period (CP). 
        #Adjust the naming of the reference time
        hsCP=helpers.timeslice(hs,
                        calCfg['calPeriodStart'],
                        calCfg['calPeriodEnd'])
        rfCP=rfCP.rename({"reftime": "time"})

        #Match calendars between reference data and simulations
        #Note that here we have chosen here to align on year when converting to/from
        #a 360 day calendar. This follows the recommendation in the xarray documentaion,
        #under the assumption that we are primarily going to be working with daily data.
        #See here for details:
        #https://docs.xarray.dev/en/stable/generated/xarray.Dataset.convert_calendar.html
        hsCP=hsCP.convert_calendar(rfCP.time.dt.calendar,
                                    use_cftime=True,
                                    align_on="year")  
        
        #We interpolate time to be on a common time axis
        hsCP=hsCP.interp(time=rfCP.time,method="nearest")
        
        #Setup mapping to methods and grouping
        cmethodsAdj={"cmethods-linear":'linear_scaling',
                "cmethods-variance":'variance_scaling',
                "cmethods-delta":"delta_method",
                "cmethods-quantile":'quantile_mapping',
                "cmethods-quantile-delta":'quantile_delta_mapping'}
        if calCfg['grouping']=="none":
            grouping="time"
        else:
            grouping="time."+calCfg['grouping']
        
        #Apply method
        if calCfg['method'] in cmethodsAdj.keys():
            raise ValueError('"cmethods" methods are currently disabled')
            from cmethods import adjust        #Use the adjust function from python cmethods
            res=adjust(method=cmethodsAdj[calCfg['method']],
                        obs=refDatCP,
                        histsimNNCP=histsimNNCP.compute(),
                        simh=histsimNNCP,
                        simp=histsimNN,
                        group="time."+calCfg['grouping'],
                        **calCfg['additionalArgs'])

        elif calCfg['method']=="cmethods-detrended":
            # Distribution methods from cmethods
            from cmethods.distribution import detrended_quantile_mapping
            raise ValueError('"cmethods-detrended" method is currently not implemented')

        elif calCfg['method']=="xclim-eqm":
            #Empirical quantile mapping -----------------------------
            from xclim.sdba import EmpiricalQuantileMapping
            EQM = EmpiricalQuantileMapping.train(rfCP, 
                                                    hsCP, 
                                                    group=grouping,
                                                    **calCfg['additionalArgs'])
            res = EQM.adjust(hs, extrapolation="constant", interp="nearest")

        elif calCfg['method']=="xclim-dqm":
            #Detrended quantile mapping -----------------------------
            from xclim.sdba import DetrendedQuantileMapping
            DQM = DetrendedQuantileMapping.train(rfCP, 
                                                    hsCP, 
                                                    group=grouping,
                                                    **calCfg['additionalArgs'])
            res = DQM.adjust(hs, extrapolation="constant", interp="nearest")

        elif calCfg['method']=="xclim-scaling":
            #Xclim - Scaling--------------------------------
            from xclim.sdba.adjustment import Scaling
            this = Scaling.train(rfCP, 
                                    hsCP,
                                    group=grouping,
                                    **calCfg['additionalArgs'])
            res = this.adjust(hs, interp="nearest")

        elif calCfg['method']=="custom":
            raise ValueError('"custom" calibration is currently not implemented')
        
        else:
            #Custom defined function
            raise ValueError(f'Unsupported calibration method "{calCfg['method']}".')
        
        #Correct output structure and Finish
        resTrans = res.transpose(*rfCP.dims)
        return resTrans
    
    # Do calibration----------------------
    # Apply function in a parallelised manner. 
    out=xr.map_blocks(func=calibrateThisChunk,
                        obj=combDS,
                        kwargs={'calCfg':calCfg},
                        template=histsimNN)

    #Finishing touches
    out2 = out.assign_attrs({"calibration_args": json.dumps(calCfg)})

    #Now write, setting the chunk sizes and compression
    chunkThisWay=[min([256,16,16][i],out2.shape[i]) for i in range(0,3)]
    out2.to_netcdf(outFile[0],
                encoding={calCfg['calibrationVariable']:{'chunksizes':chunkThisWay,
                            'zlib': True,
                            'complevel':1}})
