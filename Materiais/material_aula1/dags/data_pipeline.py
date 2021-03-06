from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sqlite3
import pandas as pd

default_args = {'owner': 'airflow'}

path = "/opt/material_aula1"
path_db_producao = path+"/data/imoveis_prod.db"
path_db_datawharehouse = path+"/data/imoveis_dw.db"
path_temp_csv = path+"/data/dataset.csv"


dag = DAG(
    dag_id='data_pipeline',
    default_args=default_args,
    schedule_interval='@daily',
    start_date=days_ago(2),
)


def _extract():
    #conectando a base de dados de produção.
    connect_db_imoveis = sqlite3.connect(path_db_producao)
    
    #selecionando os dados.
    dataset_df = pd.read_sql_query(r"""
        SELECT CIDADE.NOME as 'cidade'
       ,ESTADO.NOME as 'estado'
       ,IMOVEIS.AREA as 'area'
       ,IMOVEIS.NUM_QUARTOS
       ,IMOVEIS.NUM_BANHEIROS
       ,IMOVEIS.NUM_ANDARES
       ,IMOVEIS.ACEITA_ANIMAIS
       ,IMOVEIS.MOBILIA
       ,IMOVEIS.VALOR_ALUGUEL
       ,IMOVEIS.VALOR_CONDOMINIO
       ,IMOVEIS.VALOR_IPTU
       ,IMOVEIS.VALOR_SEGURO_INCENDIO

        FROM IMOVEIS INNER JOIN CIDADE
        ON IMOVEIS.CODIGO_CIDADE = CIDADE.CODIGO
        INNER JOIN ESTADO
        ON CIDADE.CODIGO_ESTADO = ESTADO.CODIGO;
        """, 
        connect_db_imoveis
        )
    
    #exportando os dados para a área de stage.
    dataset_df.to_csv(
        path_temp_csv,
        index=False
    )

    #fechando a conexão com o banco de dados.
    connect_db_imoveis.close()

def _transform():
    
    dataset_df = pd.read_csv(path_temp_csv)

    #transformando os dados dos atributos.
    dataset_df.aceita_animais.replace({'acept': 1, 'not acept':0}, inplace=True)
    dataset_df.mobilia.replace({'furnished': 1, 'not furnished':0}, inplace=True)

    #limpando os registros.
    dataset_df.num_andares.replace({'-': 1}, inplace=True)
    dataset_df.cidade = dataset_df.cidade.str.title()
    dataset_df.cidade.replace({ 
                        'Sao Paulo': 'São Paulo',
                        'Rio Janeiro': 'Rio de Janeiro' 
                    },
            inplace=True
    )

    dataset_df.to_csv(
        path+"/data/dataset.csv",
        index=False
    )

def _load():
    #conectando com o banco de dados Data Wharehouse.
    connect_db_imoveis_dw = sqlite3.connect(path_db_datawharehouse)
    
    #lendo os dados a partir dos arquivos csv.
    dataset_df = pd.read_csv(path_temp_csv)

    #carregando os dados no banco de dados.
    dataset_df.to_sql("imoveis", connect_db_imoveis_dw, if_exists="replace",index=False)


extract_task = PythonOperator(
    task_id="extract", python_callable=_extract, dag=dag
)

transform_task = PythonOperator(
    task_id="transform", python_callable=_transform, dag=dag
)

load_task = PythonOperator(
    task_id="load", python_callable=_load, dag=dag
)

extract_task >> transform_task >> load_task
