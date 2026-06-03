from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.compute import Pod
from diagrams.onprem.queue import Kafka
from diagrams.onprem.analytics import Flink
from diagrams.onprem.monitoring import Prometheus
from diagrams.aws.storage import S3
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.monitoring import Grafana
from diagrams.programming.language import Python

# Khởi tạo sơ đồ, lưu thành file architecture.png
with Diagram("AIOps E2E Data Layer - Payment Service", show=False, filename="architecture", direction="LR"):
    
    with Cluster("1. Service Layer"):
        services = [Pod("Checkout Service"), Pod("Payment Gateway")]
        
    with Cluster("2. Collection Layer"):
        otel = Pod("OpenTelemetry Collector")
        
    with Cluster("3. Transport Layer"):
        kafka = Kafka("Kafka Cluster")
        
    with Cluster("4. Processing Layer"):
        flink = Flink("Apache Flink\n(Streaming)")
        
    with Cluster("5. Storage Layer"):
        vm = Prometheus("VictoriaMetrics\n(Hot Storage)") # Dùng icon Prometheus thay cho VM vì tương thích
        s3 = S3("AWS S3\n(Cold Storage)")
        
    with Cluster("6. Query / ML Layer"):
        redis = Redis("Redis\n(Feature Store)")
        ml_model = Python("Anomaly Detection Model")
        grafana = Grafana("Grafana Dashboard")

    # Định nghĩa luồng chảy của dữ liệu (Data Flow)
    services >> Edge(label="Metrics/Traces") >> otel
    otel >> Edge(label="Push") >> kafka
    kafka >> Edge(label="Consume") >> flink
    
    # Từ Processing chia nhánh đi Storage và Feature Store
    flink >> Edge(label="Raw Data") >> vm
    flink >> Edge(label="Archive") >> s3
    flink >> Edge(label="Real-time Features") >> redis
    
    # Lớp Query và ML tiêu thụ dữ liệu
    redis >> Edge(label="Low-latency inference") >> ml_model
    vm >> Edge(label="Query PromQL") >> grafana