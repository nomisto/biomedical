"""
Gather dataset statistics
Help make plots
"""
from collections import Counter
from collections import defaultdict, OrderedDict
import dataclasses
import json
import os
from typing import Optional

import pandas as pd

import bigbio
from bigbio.dataloader import BigBioConfigHelpers


MAX_COMMON = 50


def gather_metadatas_json(conhelps, data_dir_base: Optional[str] = None):

    # gather configs by dataset
    configs_by_ds = defaultdict(list)
    for helper in conhelps:
        configs_by_ds[helper.dataset_name].append(helper)

    # now gather metadata
    dataset_metas = {}
    for dataset_name, helpers in configs_by_ds.items():
        print("dataset_name: ", dataset_name)

        config_metas = {}
        for helper in helpers:
            print("config name: ", helper.config.name)
            if helper.config.name in [
                "bioasq_10b_bigbio_qa",
            ]:
                continue

            if helper.is_local:
                if dataset_name == "psytar":
                    data_dir = os.path.join(
                        data_dir_base, dataset_name, "PsyTAR_dataset.xlsx"
                    )
                else:
                    data_dir = os.path.join(data_dir_base, dataset_name)
            else:
                data_dir = None

            split_metas_dataclasses = helper.get_metadata(data_dir=data_dir)
            split_metas = {}
            for split, meta_dc in split_metas_dataclasses.items():
                split_metas[split] = dataclasses.asdict(meta_dc)
                split_metas[split]["split"] = split

            config_meta = {
                "config_name": helper.config.name,
                "bigbio_schema": helper.config.schema,
                "tasks": [el.name for el in helper.tasks],
                "splits": split_metas,
                "splits_count": len(split_metas),
            }
            config_metas[helper.config.name] = config_meta

        dataset_meta = {
            "dataset_name": dataset_name,
            "is_local": helper.is_local,
            "languages": [el.name for el in helper.languages],
            "bigbio_version": helper.bigbio_version,
            "source_version": helper.source_version,
            "citation": helper.citation,
            "description": json.dumps(helper.description),
            "homepage": helper.homepage,
            "license": helper.license,
            "config_metas": config_metas,
            "configs_count": len(config_metas),
        }
        dataset_metas[dataset_name] = dataset_meta

    return dataset_metas


def flatten_metadatas(dataset_metas):

    # write flat tabular data for each schema
    flat_rows = {
        "kb": [],
        "text": [],
        "t2t": [],
        "pairs": [],
        "qa": [],
        "te": [],
    }

    for dataset_name, dataset_meta in dataset_metas.items():

        dataset_row = {
            "dataset_name": dataset_name,
            "is_local": dataset_meta["is_local"],
            "languages": dataset_meta["languages"],
            "bigbio_version": dataset_meta["bigbio_version"],
            "source_version": dataset_meta["source_version"],
            "citation": dataset_meta["citation"],
            "description": dataset_meta["description"],
            "homepage": dataset_meta["homepage"],
            "license": dataset_meta["license"],
            "configs_count": dataset_meta["configs_count"],
        }

        for config_name, config_meta in dataset_meta["config_metas"].items():

            config_row = {
                "config_name": config_name,
                "bigbio_schema": config_meta["bigbio_schema"],
                "tasks": config_meta["tasks"],
                "splits_count": config_meta["splits_count"],
            }

            print(config_name, config_meta["bigbio_schema"])

            for split, split_meta in config_meta["splits"].items():

                split_row = {}
                for key, val in split_meta.items():
                    if isinstance(val, dict):
                        split_row[key] = json.dumps(val)
                    else:
                        split_row[key] = val
                row = {**dataset_row, **config_row, **split_row}

                # e.g. kb
                schema_code = config_meta["bigbio_schema"].split("_")[1]
                flat_rows[schema_code].append(row)

    dfs = {}
    for key, rows in flat_rows.items():
        if len(rows) > 0:
            dfs[key] = pd.DataFrame(rows)
    return dfs


if __name__ == "__main__":

    # create a BigBioConfigHelpers
    # ==========================================================
    conhelps = BigBioConfigHelpers()
    conhelps = conhelps.filtered(lambda x: x.dataset_name != "pubtator_central")
    conhelps = conhelps.filtered(lambda x: x.is_bigbio_schema)

    print(
        "loaded {} configs from {} datasets".format(
            len(conhelps),
            len(set([helper.dataset_name for helper in conhelps])),
        )
    )

    do_public = True
    do_private = True

    if do_public:
        public_conhelps = conhelps.filtered(lambda x: not x.is_local)
        public_dataset_metas = gather_metadatas_json(public_conhelps)
        with open("bigbio-public-metadatas.json", "w") as fp:
            json.dump(public_dataset_metas, fp, indent=4)
        public_dfs = flatten_metadatas(public_dataset_metas)
        for key, df in public_dfs.items():
            df.to_parquet(f"bigbio-public-metadatas-flat-{key}.parquet")
            df.to_csv(f"bigbio-public-metadatas-flat-{key}.csv", index=False)

    if do_private:
        data_dir_base = "/home/galtay/data/bigbio"
        private_conhelps = conhelps.filtered(lambda x: x.is_local)
        private_dataset_metas = gather_metadatas_json(
            private_conhelps, data_dir_base=data_dir_base
        )
        with open("bigbio-private-metadatas.json", "w") as fp:
            json.dump(private_dataset_metas, fp, indent=4)
        private_dfs = flatten_metadatas(private_dataset_metas)
        for key, df in private_dfs.items():
            df.to_parquet(f"bigbio-private-metadatas-flat-{key}.parquet")
            df.to_csv(f"bigbio-private-metadatas-flat-{key}.csv", index=False)
