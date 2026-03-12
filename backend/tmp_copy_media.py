import shutil
import os

src_dir = r"f:\Dev\Projects\our_lending\Материал для сайта\Видео для страницы портфолио"
dst_dir = r"f:\Dev\Projects\our_lending\autoanswer-site\public\media"

# Create destination posters dir if needed
dst_posters = os.path.join(dst_dir, "posters")
os.makedirs(dst_posters, exist_ok=True)

files = os.listdir(src_dir)
for f in files:
    src_path = os.path.join(src_dir, f)
    if os.path.isfile(src_path):
        if f.endswith('.mp4'):
            dst_path = os.path.join(dst_dir, f)
            print(f"Copying {f} to {dst_path}")
            shutil.copy2(src_path, dst_path)
        elif f.endswith('.jpg') or f.endswith('.png'):
            dst_path = os.path.join(dst_posters, f)
            print(f"Copying {f} to {dst_path}")
            shutil.copy2(src_path, dst_path)
