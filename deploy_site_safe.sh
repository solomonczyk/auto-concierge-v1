#!/bin/bash
set -euo pipefail

# Safe deploy for bt-aistudio.ru static site.
# Keeps user-uploaded media outside release artifacts.

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 <path_to_built_site_dir>"
  exit 1
fi

SOURCE_DIR="$1"
SITE_ROOT="/var/www/studioaisolutions"
RELEASE_DIR="$SITE_ROOT/dist/client"
MEDIA_DIR="$SITE_ROOT/media"
LEGACY_MEDIA_DIR="$SOURCE_DIR/media"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "ERROR: Source dir not found: $SOURCE_DIR"
  exit 1
fi

mkdir -p "$RELEASE_DIR"
mkdir -p "$MEDIA_DIR/posters"
mkdir -p "$MEDIA_DIR/video/src"

# Deploy only app build files, never delete media storage.
rsync -a --delete --exclude "media" "$SOURCE_DIR"/ "$RELEASE_DIR"/

# Bootstrap media from legacy release folder if persistent storage is empty.
if [ -d "$LEGACY_MEDIA_DIR" ] && [ -z "$(ls -A "$MEDIA_DIR/posters" 2>/dev/null)" ]; then
  rsync -a "$LEGACY_MEDIA_DIR"/ "$MEDIA_DIR"/
fi

# Compatibility link for any legacy references inside app bundle.
ln -sfn "$MEDIA_DIR" "$RELEASE_DIR/media"

# Fast health checks for known broken posters.
required_posters=(
  "neurovideo-marketplace-cover.webp"
  "neurovideo-social-promo.webp"
  "neurovideo-product-demo.webp"
  "neurovideo-learning-lms.webp"
  "gdocs-assistant.webp"
  "hr-assistan.webp"
  "telegram-restaurant-bot.webp"
)

required_videos=(
  "neurovideo-marketplace-cover.mp4"
  "neurovideo-social-promo.mp4"
  "neurovideo-product-demo.mp4"
  "neurovideo-learning-lms.mp4"
  "gdocs-assistant.mp4"
  "hr-assistant.mp4"
)

missing_count=0
for poster in "${required_posters[@]}"; do
  if [ ! -f "$MEDIA_DIR/posters/$poster" ]; then
    echo "WARN: Missing poster: $MEDIA_DIR/posters/$poster"
    missing_count=$((missing_count + 1))
  fi
done

for video in "${required_videos[@]}"; do
  if [ ! -f "$MEDIA_DIR/video/src/$video" ]; then
    echo "WARN: Missing video: $MEDIA_DIR/video/src/$video"
    missing_count=$((missing_count + 1))
  fi
done

nginx -t
systemctl reload nginx

echo "Deploy complete."
if [ "$missing_count" -gt 0 ]; then
  echo "Done with warnings: $missing_count poster files are missing."
  exit 2
fi
