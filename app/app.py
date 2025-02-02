from flask import Flask, request, jsonify
import uuid
import os
from kubernetes import client, config

app = Flask(__name__)

# Kubernetes yapılandırmasını yükle: InCluster veya yerel kubeconfig
try:
    config.load_incluster_config()
except Exception as e:
    config.load_kube_config()

# CronJob API istemcisini oluştur
batch_v1 = client.BatchV1Api()

# Kullanılacak namespace (default olarak "default", istenirse environment variable ile değiştirilebilir)
NAMESPACE = os.getenv("NAMESPACE", "default")

# Kullanıcının verdiği interval değerini cron schedule formatına çeviren fonksiyon
def get_schedule(interval):
    mapping = {
        "1 dk": "*/1 * * * *",    # Her dakika
        "10 dk": "*/10 * * * *",  # Her 10 dakikada
        "1 saat": "0 * * * *"      # Her saat başı
    }
    return mapping.get(interval)

# Yeni CronJob oluşturma endpoint'i
@app.route('/cronjobs', methods=['POST'])
def create_cronjob():
    data = request.get_json()
    interval = data.get("interval")
    message = data.get("message")

    schedule = get_schedule(interval)
    if not schedule:
        return jsonify({"error": "Geçersiz interval. Desteklenen değerler: '1 dk', '10 dk', '1 saat'"}), 400

    # Benzersiz cron id oluştur ve CronJob ismini belirle
    cron_id = str(uuid.uuid4())
    job_name = f"cronjob-{cron_id}"

    # CronJob manifest'i (job template içinde Alpine imajı kullanılarak echo komutu çalıştırılıyor)
    cron_job_manifest = {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {"name": job_name},
        "spec": {
            "schedule": schedule,
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "restartPolicy": "OnFailure",
                            "containers": [{
                                "name": "job",
                                "image": "alpine",
                                "args": ["sh", "-c", f"echo '{message}'"]
                            }]
                        }
                    }
                }
            }
        }
    }

    try:
        batch_v1.create_namespaced_cron_job(
            body=cron_job_manifest,
            namespace=NAMESPACE
        )
        return jsonify({"cron_id": cron_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Var olan CronJob güncelleme endpoint'i
@app.route('/cronjobs/<cron_id>', methods=['PUT'])
def update_cronjob(cron_id):
    data = request.get_json()
    interval = data.get("interval")
    message = data.get("message")

    schedule = get_schedule(interval)
    if not schedule:
        return jsonify({"error": "Geçersiz interval. Desteklenen değerler: '1 dk', '10 dk', '1 saat'"}), 400

    job_name = f"cronjob-{cron_id}"

    # Güncelleme (patch) yapılacak manifest
    patch_body = {
        "spec": {
            "schedule": schedule,
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": "job",
                                "image": "alpine",
                                "args": ["sh", "-c", f"echo '{message}'"]
                            }]
                        }
                    }
                }
            }
        }
    }

    try:
        batch_v1.patch_namespaced_cron_job(
            name=job_name,
            namespace=NAMESPACE,
            body=patch_body
        )
        return jsonify({"message": "CronJob başarıyla güncellendi"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Var olan CronJob silme endpoint'i
@app.route('/cronjobs/<cron_id>', methods=['DELETE'])
def delete_cronjob(cron_id):
    job_name = f"cronjob-{cron_id}"
    try:
        batch_v1.delete_namespaced_cron_job(
            name=job_name,
            namespace=NAMESPACE,
            body=client.V1DeleteOptions()
        )
        return jsonify({"message": "CronJob başarıyla silindi"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Opsiyonel: Tüm CronJob'ları listeleyen endpoint
@app.route('/cronjobs', methods=['GET'])
def list_cronjobs():
    try:
        cronjobs = batch_v1.list_namespaced_cron_job(namespace=NAMESPACE)
        items = []
        for cj in cronjobs.items:
            # İsim formatı "cronjob-{cron_id}" olduğundan cron_id'yi çekiyoruz
            if cj.metadata.name.startswith("cronjob-"):
                cron_id = cj.metadata.name.split("cronjob-")[1]
                # Container komutunun son argümanından mesajı elde ediyoruz
                msg = cj.spec.job_template.spec.template.spec.containers[0].args[-1].strip("'")
                items.append({
                    "cron_id": cron_id,
                    "name": cj.metadata.name,
                    "schedule": cj.spec.schedule,
                    "message": msg
                })
        return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # API, 0.0.0.0:5000 adresinde dinlenecek
    app.run(host='0.0.0.0', port=5000)
