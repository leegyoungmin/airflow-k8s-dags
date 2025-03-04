"""
Kubernetes Pod Operator를 사용한 데이터 처리 파이프라인 예제
- 데이터 수집
- 데이터 전처리
- 데이터 분석
- 결과 저장
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from airflow.operators.dummy import DummyOperator
from kubernetes.client import models as k8s

# 기본 인자 설정
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2025, 3, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# 공통으로 사용할 환경 변수
env_vars = [
    k8s.V1EnvVar(name='DATA_DIR', value='/data'),
    k8s.V1EnvVar(name='LOG_LEVEL', value='INFO'),
    k8s.V1EnvVar(name='EXECUTION_DATE', value='{{ ds }}'),
]

# 공통으로 사용할 볼륨 설정
volume_config = k8s.V1Volume(
    name='data-volume',
    persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(
        claim_name='data-processing-pvc'  # PVC 이름 (미리 생성 필요)
    )
)

volume_mount_config = k8s.V1VolumeMount(
    name='data-volume',
    mount_path='/data',
    sub_path=None,
    read_only=False
)

resources = k8s.V1ResourceRequirements(
    requests = {
        'cpu': '500m',
        'memory': '512Mi'
    },
    limits = {
        'cpu': '1000m',
        'memory': '1Gi'
    }
)

# DAG 정의
dag = DAG(
    'k8s_data_pipeline',
    default_args=default_args,
    description='Kubernetes Pod Operator를 사용한 데이터 파이프라인',
    schedule_interval=timedelta(days=1),
    catchup=False,
    tags=['kubernetes', 'data_processing'],
)

# 시작
start = DummyOperator(task_id='start_pipeline', dag=dag)

# 1. 데이터 수집 태스크
collect_data = KubernetesPodOperator(
    task_id='collect_data',
    name='data-collector',
    namespace='airflow',
    image='python:3.9-slim',
    cmds=["bash", "-c"],
    arguments=["pip install pandas && python -c \"import os, pandas as pd, time, random; from datetime import datetime; print('데이터 수집 시작...'); execution_date = os.environ.get('EXECUTION_DATE'); data_dir = os.environ.get('DATA_DIR'); output_path = f'{data_dir}/raw_data_{execution_date}.csv'; num_records = 1000; data = {'id': list(range(1, num_records + 1)), 'timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S') for _ in range(num_records)], 'value1': [random.uniform(10, 100) for _ in range(num_records)], 'value2': [random.uniform(100, 1000) for _ in range(num_records)], 'category': [random.choice(['A', 'B', 'C', 'D']) for _ in range(num_records)]}; df = pd.DataFrame(data); os.makedirs(data_dir, exist_ok=True); df.to_csv(output_path, index=False); print(f'데이터 수집 완료: {num_records}개 레코드가 {output_path}에 저장되었습니다.')\""],
    env_vars=env_vars,
    volumes=[volume_config],
    volume_mounts=[volume_mount_config],
    container_resources = resources,
    is_delete_operator_pod=True,
    in_cluster=True,
    get_logs=True,
    image_pull_policy='IfNotPresent',
    dag=dag,
)

# 2. 데이터 전처리 태스크
preprocess_data = KubernetesPodOperator(
    task_id='preprocess_data',
    name='data-preprocessor',
    namespace='airflow',
    image='python:3.9-slim',
    cmds=["bash", "-c"],
    arguments=["pip install pandas scikit-learn numpy && python -c \"import os, pandas as pd, numpy as np, pickle; from sklearn.preprocessing import StandardScaler; print('데이터 전처리 시작...'); execution_date = os.environ.get('EXECUTION_DATE'); data_dir = os.environ.get('DATA_DIR'); input_path = f'{data_dir}/raw_data_{execution_date}.csv'; output_path = f'{data_dir}/processed_data_{execution_date}.csv'; model_path = f'{data_dir}/scaler_{execution_date}.pkl'; df = pd.read_csv(input_path); print(f'로드된 데이터 크기: {df.shape}'); df = df.fillna(df.mean(numeric_only=True)); Q1 = df['value1'].quantile(0.25); Q3 = df['value1'].quantile(0.75); IQR = Q3 - Q1; df = df[~((df['value1'] < (Q1 - 1.5 * IQR)) | (df['value1'] > (Q3 + 1.5 * IQR)))]; numeric_features = ['value1', 'value2']; scaler = StandardScaler(); df[numeric_features] = scaler.fit_transform(df[numeric_features]); df = pd.get_dummies(df, columns=['category']); df.to_csv(output_path, index=False); with open(model_path, 'wb') as f: pickle.dump(scaler, f); print(f'데이터 전처리 완료: 처리된 데이터가 {output_path}에 저장되었습니다.'); print(f'스케일러 모델이 {model_path}에 저장되었습니다.')\""],
    env_vars=env_vars,
    volumes=[volume_config],
    volume_mounts=[volume_mount_config],
    container_resources = resources,
    is_delete_operator_pod=True,
    in_cluster=True,
    get_logs=True,
    image_pull_policy='IfNotPresent',
    dag=dag,
)

# 3. 데이터 분석 태스크
analyze_data = KubernetesPodOperator(
    task_id='analyze_data',
    name='data-analyzer',
    namespace='airflow',
    image='python:3.9-slim',
    cmds=["bash", "-c"],
    arguments=["pip install pandas matplotlib seaborn numpy && python -c \"import os, pandas as pd, matplotlib.pyplot as plt, seaborn as sns, json; print('데이터 분석 시작...'); execution_date = os.environ.get('EXECUTION_DATE'); data_dir = os.environ.get('DATA_DIR'); input_path = f'{data_dir}/processed_data_{execution_date}.csv'; output_path = f'{data_dir}/analysis_results_{execution_date}.json'; viz_path = f'{data_dir}/correlation_heatmap_{execution_date}.png'; df = pd.read_csv(input_path); stats = {'record_count': len(df), 'columns': list(df.columns), 'numeric_stats': {}}; numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns; for col in numeric_cols: stats['numeric_stats'][col] = {'mean': df[col].mean(), 'median': df[col].median(), 'std': df[col].std(), 'min': df[col].min(), 'max': df[col].max()}; correlation_matrix = df.select_dtypes(include=['float64', 'int64']).corr().round(2); plt.figure(figsize=(10, 8)); sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm'); plt.title('Feature Correlation Heatmap'); plt.tight_layout(); plt.savefig(viz_path); stats['correlation_matrix'] = correlation_matrix.to_dict(); stats['visualization_path'] = viz_path; with open(output_path, 'w') as f: json.dump(stats, f, indent=2, default=str); print(f'데이터 분석 완료: 분석 결과가 {output_path}에 저장되었습니다.'); print(f'시각화 결과가 {viz_path}에 저장되었습니다.')\""],
    env_vars=env_vars,
    volumes=[volume_config],
    volume_mounts=[volume_mount_config],
    container_resources = resources,
    is_delete_operator_pod=True,
    in_cluster=True,
    get_logs=True,
    image_pull_policy='IfNotPresent',
    dag=dag,
)

# 4. 결과 저장 태스크
store_results = KubernetesPodOperator(
    task_id='store_results',
    name='result-storer',
    namespace='airflow',
    image='python:3.9-slim',
    cmds=["bash", "-c"],
    arguments=["pip install pandas && python -c \"import os, pandas as pd, json, shutil; from datetime import datetime; print('결과 저장 시작...'); execution_date = os.environ.get('EXECUTION_DATE'); data_dir = os.environ.get('DATA_DIR'); processed_path = f'{data_dir}/processed_data_{execution_date}.csv'; analysis_path = f'{data_dir}/analysis_results_{execution_date}.json'; archive_dir = f'{data_dir}/archive/{execution_date}'; summary_path = f'{data_dir}/pipeline_summary_{execution_date}.txt'; df = pd.read_csv(processed_path); row_count = len(df); col_count = len(df.columns); with open(analysis_path, 'r') as f: analysis_results = json.load(f); with open(summary_path, 'w') as f: f.write(f'데이터 파이프라인 실행 요약 - {execution_date}\\n'); f.write(f'===================================\\n\\n'); f.write(f'처리된 레코드 수: {row_count}\\n'); f.write(f'특성 수: {col_count}\\n\\n'); f.write(f'주요 통계:\\n'); for col, stats in analysis_results.get('numeric_stats', {}).items(): f.write(f'  {col}:\\n'); for stat_name, stat_value in stats.items(): f.write(f'    {stat_name}: {stat_value}\\n'); f.write('\\n'); f.write(f'\\n파이프라인 완료 시간: {datetime.now()}\\n'); os.makedirs(archive_dir, exist_ok=True); for file_name in os.listdir(data_dir): if execution_date in file_name and os.path.isfile(os.path.join(data_dir, file_name)): shutil.copy(os.path.join(data_dir, file_name), os.path.join(archive_dir, file_name)); print(f'결과 저장 완료: 파이프라인 요약이 {summary_path}에 저장되었습니다.'); print(f'결과 파일이 {archive_dir}에 아카이브되었습니다.')\""],
    env_vars=env_vars,
    volumes=[volume_config],
    volume_mounts=[volume_mount_config],
    container_resources = resources,
    is_delete_operator_pod=True,
    in_cluster=True,
    get_logs=True,
    image_pull_policy='IfNotPresent',
    dag=dag,
)

# 종료
end = DummyOperator(task_id='end_pipeline', dag=dag)

# 태스크 의존성 설정
start >> collect_data >> preprocess_data >> analyze_data >> store_results >> end