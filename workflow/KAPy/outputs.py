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

import sqlite3
import pandas as pd
import os


"""
ensstats=wf['database']['ensstats']
members=wf['database']['members']
outFile=os.path.join(config['dirs']['outputs'],'KAPy_outputs.sqlite')
"""

def writeToDatabase(config, ensstats, members, outFile):
    #Load data file function
    def loadDataFiles(inFiles):
        dat = []
        for f in inFiles:
            datIn=pd.read_csv(f)
            datIn.insert(0,'sourcePath',f)
            datIn.insert(0,'filename',os.path.basename(f))
            dat += [datIn]
        datdf = pd.concat(dat)
        
        #Split out the defined elements
        datdf.insert(2,'expt',datdf['filename'].str.extract("^[^_]+_[^_]+_[^_]+_([^_]+)_.*$"))
        datdf.insert(2,'gridID',datdf['filename'].str.extract("^[^_]+_[^_]+_([^_]+)_.*$"))
        datdf.insert(2,'datasetID',datdf['filename'].str.extract("^[^_]+_([^_]+)_.*$"))
        datdf.insert(2,'indID',datdf['filename'].str.extract("^([^_]+)_.*$"))

        #Drop the filename
        datout=datdf.drop(columns=['filename','sourcePath','index'])
        return(datout)
    
    #Load data
    esDat=loadDataFiles(ensstats)
    memDat=loadDataFiles(members)

    # Connect to (or create) a SQLite database
    conn = sqlite3.connect(outFile[0])

    # Write DataFrames to separate tables
    esDat.to_sql("Ensemble_statistics", conn, if_exists="replace", index=False)
    memDat.to_sql("Ensemble_members", conn, if_exists="replace", index=False)

    #Set indexing
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX idx_ensstats ON Ensemble_statistics(indID,datasetID,gridID,expt,seasonID,periodID,percentiles,areaID)")
    cursor.execute("CREATE INDEX idx_members ON Ensemble_members(expt, gridID,datasetID,indID,areaID,seasonID,periodID)")

    # Commit and close
    conn.commit()
    conn.close()

    #Write a csv version as well
    esDat.to_csv(os.path.join(config['dirs']['outputs'],"Ensemble_statistics.csv"),index=False)
    memDat.to_csv(os.path.join(config['dirs']['outputs'],"Ensemble_members.csv"),index=False)



