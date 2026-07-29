import os, sys, time, glob
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

load_dotenv()
key = os.environ.get("TWELVELABS_API_KEY")
if not key:
    sys.exit("TWELVELABS_API_KEY not set — put it in .env")

client = TwelveLabs(api_key=key)

clip = sys.argv[1] if len(sys.argv) > 1 else sorted(
    glob.glob("video/*.mp4"), key=os.path.getsize
)[0]
size_mb = os.path.getsize(clip) / 1e6
print(f"clip: {clip}\nsize: {size_mb:.1f} MB")

index = client.indexes.create(
    index_name=f"gatwick-{int(time.time())}",
    models=[
        {"model_name": "marengo3.0", "model_options": ["visual", "audio"]},
        {"model_name": "pegasus1.2", "model_options": ["visual", "audio"]},
    ],
)
print(f"index: {index.id}")

t0 = time.time()
with open(clip, "rb") as f:
    task = client.tasks.create(index_id=index.id, video_file=f)
upload_done = time.time() - t0
print(f"upload: {upload_done:.1f}s  task: {task.id}")

last = None
while True:
    task = client.tasks.retrieve(task_id=task.id)
    if task.status != last:
        print(f"  [{time.time() - t0:6.1f}s] {task.status}")
        last = task.status
    if task.status in ("ready", "failed"):
        break
    time.sleep(5)

total = time.time() - t0
print(f"\nstatus: {task.status}")
print(f"TOTAL: {total:.1f}s for {size_mb:.1f} MB")
