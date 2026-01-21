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
Since there there are three stages to follow, create these three folders and name them ```1.first_KAPy_computation```, ```2.bc_Python_computation``` and ```3.final_KAPy_computation```. In the folder ```1.``` and ```3.```, place the KAPy source code and in folder ```2.```, place the python bas correction file found [here](Tutorial07_files/indicators.tsv). 

### Stage one
1. Here, we want to generate the aggrgated files of each model to make them range from historical to end of cenutury. We do this in KAPy using the first rule of the KAPy snakemake primVar. Enter the ```1.first_KAPy_computation``` folder. Place your input files of tas, tmax and tmin of all the models and the reference data in the ```/inputs/``` folder. Instead of copying these files, you can just symbolicaly link  ```ln -s```  them from where therey are to avoid having too many duplicates of the same data. 
2. In the ```config/config.csv```, make sure the pickle part is switched off so that you generate the ```.nc``` files instead of the default ```.pkl``` files. The rest of the parts and file are not important at this stage as we are going to force KAPy to only run the first rule which onky generates the primary variables ie aggregating the model files of each model which are time fragmeneted. Thus, here only interested in files generated in placed in ```/outputs/1.variables/```
3. To check if everything is set correctly set, do a ```dry-run``` of KAPy remembering to force to only check for the first rule .. which you should specify when commanding the dry run:
 
```
snakemake -n primVar
```
4. If all is well, KAPy will tell you (show you on the screen) what steps it will follow to generate the files you want. Tf satisfied, then run KAPy specifying the number of cores you want to use (and available) to generate the files and this weill generate and place files into ```/outputs/1.variables/```:
```
snakemake --cores 8 primVar
```
5. Then leave the ```1.first_KAPy_computation``` folder to prepare for the next stage. 

### Stage two
This stage involves uisng Python outside KAPy to bias correct tmean, tmax and tmin together to ensure logical relationship amongst them is maintained after bias corection i.e ```tmin < tmean <tmax```.
1. Enter the stage two folder ```2.bc_Python_computation```. Cretae a folder to place the outouts of this stage ```mkdir /processed```.
2. Make sure the Python code has the correct patrts of the input data and where ro save the outputs. Here, the input data is the output of the first stage. Thus, the path for the input files should point to
```
../1.first_KAPy_computation/outputs/1.variables
```
3. Then the output path should point to ``` /processed ```. These output files will be used as input of the next stage.


### Stage three
This is the final stage where KAPy shines to generate indicators and related future statistics linke dto tmin, tmean and tmax.

1. We use the bias corrected files created in stage two ```/2.bc_Python_computation/processed/``` as inputs of this stage. Create the input folder and subfolders of tas, tmin and tmax.
   ```
   mkdir -p outputs/1.variables/tas
   ```
   do this also for tmin and tmax
2. Inside each subfolder, sym link related files sourcing them from the stage two ```processed``` folder
3. Make sure also the era5 (reference data) files are also placed in the subfolders and these you can source them from ```/1.first_KAPy_computation/outputs/1.variables/---```. You wont fond the era5 files in Stage two because we dont bias correct them
4. Since for KAPy to run, it expects files to be present in the ```/inputs/``` folder otherwise it complains.Thus we can trick it by placining inpute files in there but which it will not use since we want KAPy to use the already present files in ```outputs/1.variables```. So we put the files which were used to generate the ```1.variables``` in the input foler. We We do this ny sym linking them from the input folder of ```1.first_KAPy_computation``` in stage one.
5. After we do this, we expect KAPy to skip the gereation of the primVar files as they already exist. To test this, do a ```dry run``` first and you should see that amongst the jobs KAPy will do, the primVar one is not there.
```
snakemake -n
```
If satisfied, then run the full KAPy

```
snakemake --cores 8
```
6. Remember if for some reason, KAPy stops and you wnat to continue again after solving the problem, you can use the following rerun-incomplete command (or sometimes you need to start by unlocking snakemake first)
```
snakemake --unlock
```
```
snakemake --cores 8 --rerun-incomplete
```

6. That concludes this tutorial. This is a temporary way of getting the bias corrected tmax and tmin files which si done outside KAPy. The plan is to implement this in KAPy in the near future.

