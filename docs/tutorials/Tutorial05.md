# Tutorial 5 - Using a shapefile for area averaging

## Goal

To learn how a new shapefile is coupled configured in KAPy.

## What are we going to do?

In this tutorial we will use a shapefile to calculate averages over regions of interest, in this case the regions of Ghana.


## Point of departure

This tutorial follows on directly from the end of [Tutorial 1](Tutorial01.md).

## Instructions

1. In Tutorial 1, you performed a complete run of a KAPy pipeline, starting from a fresh installation.
That configuration calculates area statistics over the entire domain of the analysis. In a real setting, however, we are often interested in calculating statistics over polygons such as municipalities, regions, drainages or national boundaries, as defined in a *shapefile*.

2. In a real setting when you have a shapefile to use for your case, you will need to couple it into KAPy via arguments in the config file `./config/config.yaml`. The two arguememts you specify are the path where the shapefile is located (the )`shapefile` argument) and the `idColumn` name used by KAPy to identify unique codes for each polygon. A convenient location you can place a shapefile folder is in `./input/`.

However, for the sake of this tutorial in consistency with the domain used in the previous tutorials, we will use a Ghana shapefile found [here](Tutorial05_files). A shapefile is not a single file but a collection of several files with different extensions, working together to represent spatial data. You can see these file extentions by:

```
ls ./docs/tutorials/Tutorial05_files/*
```

3. The shapefile is coupled into KAPy via arguments in the config file `./config/config.yaml`. Open this file in a text editor (e.g. `vi`). The path of the shapefile is specified under the `arealstats` category. The `shapefile` option gives the path to the shapefile (normally by pointing to the `*.shp` file. The `idColumn` option gives the name of the unique identifier of each polygon stored in the shapefile - you can find the name of this column by opening the shapefile in a GIS client or by using GeoPandas. A shapefile for Ghana is stored in the helper files for Tutorial05 - edit the configuration file to include these options, so that it looks like this:

```
# Configuration options------------------------------------
arealstats:
    useAreaWeighting: True
    shapefile: 'docs/tutorials/Tutorial05_files/Ghana_regions.shp'
    idColumn: 'ADM1_PCODE'
```

4. So now we are ready to go.

   Firstly, let's see how snakemake responds to this new configuration. 

```
snakemake -n
```
KAPy will show that it needs to do a lot of things to effect these changes, but primarily in relation to recalculating the arealstatistics and the output plots. 

5. The revised DAG is also even more complicated as a result. Open the file `dag_tutorial05.png` and compare it to the previous DAGs.

```
snakemake --dag | dot -Tpng -Grankdir=LR > dag_tutorial05.png
```

6. Then, make it so!

```
snakemake --cores 1
```

7.  The averages over each area are stored in the `outputs/6.areal_statistics/ArealStatistics.csv` output file. Open this in a spreadsheet to see the results for each region in Ghana. You can also try plotting the results by combining them with the shapefile.

8. You can perform a more detailed analysis on your own using e.g. `Python`, `R` or your programming language of choice. We have included a Python example, that can be downloaded from [here](Tutorial05_files/plot_regions.py). You can run the script as follows:
```
python docs/tutorials/Tutorial05_files/plot_regions.py
```

9. The output file from the script can be found in `Tutorial05.png`. Opening it in a graphics viewer, you will see how the temperature changes across regions in Ghana under climate change.

10. That concludes this tutorial. 
