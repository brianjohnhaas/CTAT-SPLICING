#!/usr/bin/env python

import sys, os, re
import typing
import sqlite3
import logging
import collections
from collections import defaultdict
import argparse
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():

    parser = argparse.ArgumentParser(description="examines intron feature usage stats and computes the normalized abundance", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("--sqlite3_db", dest="sqlite3_db", type=str, required=True, help="sqlite3_db name")
    parser.add_argument("--intron_features_file", dest="intron_features_file", type=str, required=True, help="file containing list of intron features")
    parser.add_argument("--output_file", dest="output_file", type=str, required=True, help="output filename")
    
    args = parser.parse_args()
    sqlite3_dbname = args.sqlite3_db
    intron_features_file = args.intron_features_file
    output_filename = args.output_file

    conn = sqlite3.connect(sqlite3_dbname)
    c = conn.cursor()

    ## get counts of samples according to tissue type
    query = "select db_class, sample_type, count(*) from samples group by db_class, sample_type"
    #logger.info(query)
    c.execute(query)
    rows = c.fetchall()
    sample_type_counts = defaultdict(int)
    for row in rows:
        (db_class, sample_type, count) = row
        sample_type = "^".join([db_class, sample_type])
        sample_type_counts[sample_type] += count
        base_sample_type = "^".join([db_class, "total"])
        sample_type_counts[base_sample_type] += count


    ofh = open(output_filename, 'wt')

    with open(intron_features_file) as fh:
        for intron_feature in fh:
            intron_feature = intron_feature.rstrip()
            logger.info(intron_feature)
            start_time = time.time()

            examine_intron_feature_usage_stats(intron_feature, c, sample_type_counts, ofh)

            end_time = time.time()
            seconds = int(end_time - start_time)
            logger.info("-took {} seconds".format(seconds))

    
    ofh.close()

    sys.exit(0)



def examine_intron_feature_usage_stats(intron_feature : str,
                                       c : sqlite3.Cursor,
                                       sample_type_counts : collections.defaultdict,
                                       ofh : typing.TextIO):


    MIN_TOTAL_READ_MAPPINGS = 5 # based on a handful of known cancer introns.
    
    query = str("select s.sample_name, s.db_class, s.sample_type, s.total_uniq_count, s.total_count, "
                + " io.intron, io.unique_mappings, io.all_mappings "
                + " from samples as s, intron_occurrence as io "
                + " where s.sample_name = io.sample "
                + "       and io.intron = \"{}\" ".format(intron_feature)
                + "       and io.all_mappings >= {} ".format(MIN_TOTAL_READ_MAPPINGS)
                + "       and not (db_class = \"TCGA\" and TN = \"N\") ")  # skip the tumor normals for now... analyze separately.
                

    #print(query)
    #exit(0)
    
    c.execute(query) #, (intron_feature, MIN_TOTAL_READ_MAPPINGS))

    rows = c.fetchall()


    sample_type_counter = dict()
    def add_to_counter(sample_grp_type : str, category : str):
        if sample_grp_type not in sample_type_counter:
            sample_type_counter[sample_grp_type] = defaultdict(int)
        sample_type_counter[sample_grp_type][category] += 1
        return
    

    for row in rows:
        (sample_name, db_class, sample_type, sample_total_uniq_count, sample_total_count,
         intron_token, intron_unique_mappings, intron_all_mappings) = row


        ## simple counting intron occurrences according to sample type
        specific_sample_type = "^".join([db_class, sample_type])
        base_sample_type = "^".join([db_class, "total"])

        if intron_unique_mappings != 0:
            add_to_counter(specific_sample_type, "intron_unique_mappings")
            add_to_counter(base_sample_type, "intron_unique_mappings")

        if intron_all_mappings != 0:
            add_to_counter(specific_sample_type, "intron_all_mappings")
            add_to_counter(base_sample_type, "intron_all_mappings")


    ## report on findings.
    categories = ("intron_unique_mappings", "intron_all_mappings")
    

    for sample_grp_type, counter_dict in sample_type_counter.items():
        db_class, sample_type = sample_grp_type.split("^")
        output = [intron_token, db_class, sample_type]


        num_sample_counts = sample_type_counts[sample_grp_type]
        
        for cat in categories:
            num_cat = counter_dict.get(cat, 0)
            frac_cat = num_cat / num_sample_counts
            output += [str(num_cat), "{:.4f}".format(frac_cat)]
            
        print("\t".join(output), file=ofh)
    
    ofh.flush()
    

if __name__ == '__main__':
    main()






