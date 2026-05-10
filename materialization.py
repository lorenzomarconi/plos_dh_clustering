from _utils import *
import pandas as pd
import psycopg2
from io import StringIO

def materialize_dataset(
        df=None,
        csv_filepath=None,
        table_name=None,
        attribute2datatype=None,
        csv_dtype={},
        csv_header=0,
        create_index_on_patient_key=True
    ) :
    assert not (df is None and csv_filepath is None)
    assert not table_name is None
    assert not attribute2datatype is None

    full_table_name = CLUSTERING_DB_NAME + "." + table_name 

    logger.info(f"Materializing data to table '{ full_table_name }'")
    if df is None :
        df = pd.read_csv(csv_filepath, dtype=csv_dtype, header=csv_header)
    assert len(attribute2datatype) == df.shape[1]

    # Establish the connection to the PostgreSQL database
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    materialize_flag = False
    append_request = input(f"If table '{ full_table_name }' exists, do you want to append new data into it? (y/n): ").strip().lower() == 'y'
    if append_request :
        materialize_flag = True
    else :
        delete_request = input(f"Do you want to overwrite (DROP and CREATE) table '{ full_table_name }'? (y/n): ").strip().lower() == 'y'
        if delete_request :
            cur.execute(f"""
                DROP TABLE IF EXISTS { full_table_name };
            """)
            materialize_flag = True

    if materialize_flag :
        # Create a new table in the PostgreSQL database
        sql_attr2dtype = ','.join([f'\n\t{attr} {dtype}' for (attr, dtype) in attribute2datatype.items()])
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS { full_table_name } ( { sql_attr2dtype} );
        """)

        # Convert the dataframe to a CSV-like object in memory
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, header=False)
        csv_buffer.seek(0)

        # Bulk insert the data into the PostgreSQL table
        cur.copy_expert(f"COPY { full_table_name } FROM STDIN WITH CSV", csv_buffer)
        
        if create_index_on_patient_key :
            # Create an index on the table
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS { table_name }_idx_patient
                ON { full_table_name }(idcentro, idana);
            """)
    logger.info(f"Skipped materialization of table '{ full_table_name }'")

    # Commit the transaction and close the connection
    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Data successfully inserted into { table_name }")