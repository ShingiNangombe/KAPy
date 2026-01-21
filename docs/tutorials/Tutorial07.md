# Tutorial 7 - Multi-variable Bias correction of tmax and tmin and generation of related climate statistics

## Goal

To implement bias calibration of ```tmax``` and ```tmin``` together making sure tmax is never lower than tmin after correction. Then generation of bias corrected products.

## What are we going to do?

In this tutorial we implement a bias-correction of tmax and tmin together. We use the simulated monthly tmax and tmin from ```CORDEX``` over ```Ghana```, and correct against ```ERA5``` as the observational reference dataset. Here, the correction is done outside KAPy (using ```Python```) with the intention of incooperating it in KAPy in the future. We the use the bias corrected data and running through KAPy to generate climate change statisctics in the form of NetCDF and CSV files. A summary of the steps followed are:

 Generate the files which are time merged from 1950 to 2100. Its best to do this using KAPy since the first rule of the KAPy snake ḿake does exactly that. 
  
  Using files gerated as input files, do the bias correctiing using the Pythin script provided here, do the bias correction of tmean, tmax and tmin together. Make sure the paths in the script are pointing to your data. This will geretae the bias corrected files.

 Now place the bias corrected files in a new KAPy folder and then run run KAPy to produce the indicators and the related areaal statistics in the for  of csv and NetCDF files.

## Point of departure

This tutorial follows but is not linked to [Tutorial 06](Tutorial06.md).

## Background 

This tutorial performs bias-correction using the `quantile delta mapping` approach from the `xclim python` package. More information on the method can be found [here](https://xclim.readthedocs.io/en/stable/notebooks/sdba.html).
To make sure tmax is never < tmin at any time after bias adjustment i.e to maintain the relative relationship between the two variables at once, we introduce a bias correctioin protocola which bias adjusts tmean, tmax and tmin together using diurnal temperature and skewness of the data. The approch followed to do this correcting follows the steps below and are implement through a Python script outside KAPy for now:

=> The modelled daily temperature range 
```
DTR = Tmax − Tmin
```
was QQ-scaled against gridded observations, resulting in DTRBA. All instances where ```DTRBA < 0``` were hard set to 0.

=> Then skew is computed where skewness is Z. Here the model Z is estimated then QQ-scaled against gridded observations, resulting in ZBA
```
Z = Tmean − (Tmax + Tmin)/2
```

=> Finally, the bias adjusted Tmin and Tmax were then calculated using the equations 
```
Tmin_BA =Tmean_BA − ZBA − DTRBA/2
```
and 
```
Tmax_BA = Tmean_BA − ZBA + DTRBA/2
```

## Detailed Instructions
Since there there are three stages to follow, create these three folders and name them ```1.First_KAPy```, ```2.Python_bias_correction``` and ```3.Second_KAPy```. In the folder ```1.``` and ```3.```, place the KAPy source code and in folder ```2.```, place the python bas correction file found [here](Tutorial07_files/indicators.tsv). 
### Stage one
1. Here, we want to generate the aggrgated files of each model to make them range from historical to end of cenutury. We do this in KAPy using the first rule of the KAPy snakemake primVar. Enter the ```1.First_KAPy``` folder. Place your input files of tas, tmax and tmin of all the models and the reference data in the ```/inputs/``` folder. Instead of copying these files, you can just symbolicaly link ``ln -s```  them from where therey are to avoid having too many duplicates of the same data. 
2. In the ```config/config.csv```, make sure the pickle part is switched off so that you generate the ```.nc``` files instead of the default ```.pkl``` files. The rest of the parts and file are not important at this stage as we are going to force KAPy to only run the first rule which onky generates the primary variables ie aggregating the model files of each model which are time fragmeneted. Thus, here only interested in files generated in placed in ```/outputs/1.variables/```
3. To check if everything is set correctly set, do a ```dry-run``` of KAPy remembering to force to only check for the first rule .. which you should specify when commanding the dry run:
 
```
snakemake -n primVar
```
If all is well, KAPy will tell you (show you on the screen) what steps it will follow to generate the files you want.
4. Tf satisfied, then run KAPy specifying the number of cores you want to use (and available) to generate the files and this weill generate and place files into ```/outputs/1.variables/```:
```
snakemake --cores 8 primVar
```
Then leave the ``1.First_KAPy``` folder to prepare for the next stage. 

2. The calibration methods are defined and configured via `./config/calibration.tsv` which is already available and configured correctly in a default install of KAPy. Open this file in a spreadsheet (e.g. LibreOffice) and have a look. Here you will see that the definition of a calibrated variable called `tas-cal`. This  output variable is based on using `tas` from `CORDEX` as the datasource, and is calibrated against `ERA5` as the reference source, using the period 1981-2010 as the reference. The calibration method is set in the `method`column to `xclim-scaling`, while the `grouping` argument is set to `month`, indicating that we should perform the calibration individually on months.  Note also under `additionalArgs` that we are passing a dict with `kind='+'` to use calibration in the additive mode - this is appropriate for temperature, but a multiplicative model `kind= '*'` would be more appropriate for precipitation. 

3. Next, we want to be able to use the new variable that we have created, `tas-cal` in generating indicators. A new indicator table can be downloaded from [here](Tutorial06_files/indicators.tsv). Save the file over the top of the old  indicator table `./config/indicators.tsv`, then open the file using a spreadsheet. The table includes the definition of two indicators: `101-nocal` is the annual average of the raw model output temperature `tas`, while `101-scaling` is the annual average of the same data after calibration (as stored in the `tas-cal` variable). 

4. So now we are ready to go. Firstly, let's see how snakemake responds to this new configuration.
```
snakemake -n

```
5. We get a list of what Snakemake wants to do - in particular note the generation of the two versions of indicator 101. Now run the pipeline:
```
snakemake --cores 1
```

6. Once the output has been completed, you can see the new set of calibrated variables have appeared in the `calibration`directory  e.g.,
```
ls ./outputs/2.calibration/*
```

7. Output plots for 102 are also generated automatically. Try browsing the plots in a viewer e.g
```
eog ./outputs/7.plots/*
```

8. Do a quick comparison of the outputs derived with and without calibration. In `101-scaling` you will see that the CORDEX values in `101-nocal` have been moved to align with the ERA5 values e.g. the mean values for CORDEX rcp85 in 1950 are arond 298K in `101-nocal` but have been shifted to around 300 K in `101-scaling`.

9. You can perform a more detailed analysis on your own using e.g. `Python`, `R` or your programming language of choice. We have included a Python example, that can be downloaded from [here](Tutorial06_files/compare_calibration.py). You can run the script as follows:
```
python docs/tutorials/Tutorial06_files/compare_calibration.py
```
10. The script writes an output figure `Tutorial06.png` to the KAPy root directory. Opening if with an image viewer, you will see the shift in the mean temperature between the `nocal` and `scaling` indicators more clearly (in this case for the RCP8.5) scenario. Note also the close agreement between ERA5 and `CORDEX-101-scaling` during the calibration period 1981-2010.

11. That concludes this tutorial. KAPy is currently  limited to these three calibratiopn methods, but within a short time, more methods will be added.

