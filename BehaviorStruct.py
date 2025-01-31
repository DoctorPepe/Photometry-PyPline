import numpy as np
import pandas as pd
import openpyxl
import math

class BehaviorData:
    def __init__(self, id_eventsDict = {}, mpcDF = None, dlcData = None, threshold = 0.6, fps = 30):
        #dataframes
        self.mpc_data = mpcDF
        self.dlc_data = dlcData
        self.dlc_TTL = None
        self.dlc_cleaned = None
        self.dlc_alignedEvents = {}
        #events
        self.id_events = id_eventsDict
        #labeling confidence threshold
        self.threshold = threshold
        #fps of recording
        self.fps = fps

    def processEvent(self, eventID, part, baseline, outcome):
        # get the timestamps for each event with ID
        events = self.getMPCTimes(eventID)
        pName = part + "_Vel"
        for y in range(len(events)):
            # find closest DLC-TTL event to behavioral event
            closest = self.dlc_TTL.sub(events[y]).abs().idxmin()
            closest = closest['onset']
            offset = self.dlc_TTL.at[closest, 'offset_MPC']
            tMin = events[y] - baseline + offset
            tMax = events[y] + outcome + offset

            #find closest timepoints in DLC data to start and stop times
            min = self.dlc_cleaned.iloc[self.dlc_data.index.get_loc(tMin)]
            max = self.dlc_cleaned.iloc[self.dlc_data.index.get_loc(tMax)]

            print(min)
            print(max)

            #trace = self.dlc_cleaned.iloc[tMin:tMax][pName]
            #print(trace)

    def getMPCTimes(self, timestampID):
        if self.mpc_data is not None:
            tmp = self.mpc_data[self.mpc_data.ID == timestampID].secs
            return tmp.values
        else:
            raise UserWarning("Cannot retrieve timestamps from empty Med-pc dataframe. Does the original data include Med-Pc Data?")

    #aligns segment of data to each type of event using the id_eventsDict
    def alignEvents(self, part, baseline = 10, outcome = 10):
        if len(self.id_events) < 1:
            print("Error: No dictionary of events provided. Cannot align events.")
        else:
            #first, calculate offsets of each TLL pulse detected by camera compared to each TrialStart
            MPC = self.getMPCTimes(self.id_events.get("id_trialStart"))
            for x in range(len(MPC)):
                closest = self.dlc_TTL.sub(MPC[x]).abs().idxmin()
                closest = closest['onset']
                offset = self.dlc_TTL.at[closest, 'onset'] - MPC[x]
                self.dlc_TTL.at[closest, 'offset_MPC'] = offset

            self.processEvent(34, part, baseline, outcome)

            #loop though event dictionary to process each event, using TTL offsets to align animal velocity
            #vals = list(self.id_events.values())
            #for x in range(len(vals)):
                #eventName = self.id_events[x]
                #eventName = eventName.split("_")
                #eventName = eventName[1]

    def calcVel(self, df):
        vel = np.array([])
        vel = np.append(vel, 0)
        for x in range(1, int(df.shape[0] - 1)):
            if df.iloc[x, 0] is None or df.iloc[x, 1] is None:
                vel = np.append(vel, np.nan)
            else:
                #calculate euclidian distance
                dist = math.sqrt(math.exp((df.iloc[x, 0] - df.iloc[x-1, 0])) + (math.exp(df.iloc[x, 1] - df.iloc[x-1, 1])))
                vel = np.append(vel, dist)

        #calculate moving average for a 10 sample windwow
        test = np.convolve(vel, np.ones(10), 'valid') / 10
        #first 5 and last 5 samples cannot be calculated, so pad array so that dimensions fit with existing data
        test = np.concatenate([[0, 0, 0, 0, 0], test, [0,0,0,0,0]])

        return test



    def clean(self):
        #rename columns in original dataframe
        self.dlc_data.columns = (self.dlc_data.iloc[0] + '_' + self.dlc_data.iloc[1])
        self.dlc_data = self.dlc_data.iloc[2:].reset_index(drop=True)
        #change index's to reflect time in seconds instead of frame number
        self.dlc_data['Time'] = self.dlc_data.index / self.fps
        self.dlc_data.set_index('Time', inplace=True)
        #process each part independently, and remove coordinate pairs which fall below confidence threshold
        self.dlc_cleaned = self.dlc_data[["Nose_x"]]
        for x in range(0, int(self.dlc_data.shape[1]), 3):
            tmp = self.dlc_data.iloc[:, x:x+3]
            tmp = tmp[tmp.iloc[:, 2] >= self.threshold]
            pName = tmp.columns[0].split("_")
            pName = pName[0]
            pName = pName + "_Vel"
            tmp[pName] = self.calcVel(tmp)
            self.dlc_cleaned = pd.concat([self.dlc_cleaned, tmp], axis=1)

        #drop first placeholder column
        self.dlc_cleaned = self.dlc_cleaned.iloc[:, 1:]

        #rename DLC-TTL data columns
        self.dlc_TTL.columns = ['onset', 'offset']

    def readData(self, fpath):
        timestampData = None
        DLCData = None
        DLCFrames = None
        #look for Med-Pc Data
        try:
            timestampData = pd.read_excel(fpath, sheet_name="Med-Pc", header=0)
        except:
            print("Warning: Could not find Med-Pc data in file. Is there an excel tab labeled 'Med-Pc'?")

        #look for DLC Data
        try:
            DLCData = pd.read_excel(fpath, sheet_name="DLC", header=0, index_col=0)
        except:
            print("Warning: Could not find DeepLabCut data. Is there an excel tab labeled 'DLC'?")

        # look for DLC Data
        try:
            DLCTTL = pd.read_excel(fpath, sheet_name="DLC-TTL", header=0, index_col=0)
        except:
            print("Warning: Could not find DeepLabCut Recording TTL timestamps. Is there an excel tab labeled 'DLC-TTL'?")

        self.mpc_data = timestampData
        self.dlc_data = DLCData
        self.dlc_TTL = DLCTTL
