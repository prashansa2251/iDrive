#!/bin/bash

# Define container and image name
CONTAINER_NAME="idrive-container"
IMAGE_NAME="idrive"
VERSION_FILE="version.txt"

# Define Nginx config paths
LIVE_CONF="/etc/nginx/sites-enabled/cwrm.wasca.in"
MAINTENANCE_CONF="/etc/nginx/sites-available/maintenance.conf"

echo "🚀 Updating the server..."

# Switch to maintenance mode
echo "🔧 Switching to maintenance mode..."
sudo unlink "$LIVE_CONF" 2>/dev/null
sudo ln -sf "$MAINTENANCE_CONF" "$LIVE_CONF"
sudo nginx -s reload
echo "✅ Maintenance mode enabled."

# Pull the latest changes from Git
echo "📥 Pulling latest changes from Git..."
git pull || { echo "❌ Git pull failed!"; exit 1; }

# Increment version
if [ -f "$VERSION_FILE" ]; then
    VERSION=$(cat "$VERSION_FILE")
    NEW_VERSION=$(awk "BEGIN {printf \"%.1f\", $VERSION + 0.1}")
    echo "$NEW_VERSION" > "$VERSION_FILE"
    echo "🔹 Current Version: $VERSION"
    echo "🔹 Updated Version: $NEW_VERSION"
else
    echo "⚠️ Warning: $VERSION_FILE not found! Creating a new version file with 1.0."
    echo "1.0" > "$VERSION_FILE"
fi

# Commit the updated version file
git add "$VERSION_FILE"
git commit -m "🔄 Auto-incremented version to $NEW_VERSION"
git push || { echo "❌ Git push failed!"; exit 1; }

# Stop and remove the existing Docker container
echo "🛑 Stopping the running container..."
docker stop $CONTAINER_NAME 2>/dev/null
echo "🗑 Removing the old container..."
docker rm $CONTAINER_NAME 2>/dev/null

# Remove unused images (dangling images)
echo "🗑 Removing unused Docker images..."
docker image prune -f

# Remove old versions of the image
echo "🗑 Removing old Docker images of $IMAGE_NAME..."
docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | grep "^$IMAGE_NAME" | awk '{print $2}' | xargs -r docker rmi -f

# Remove unused build cache
echo "🗑 Clearing unused build cache..."
docker builder prune -f

# Build a new Docker image
echo "🛠 Building a new Docker image..."
docker build --no-cache -t $IMAGE_NAME . || { echo "❌ Docker build failed!"; exit 1; }

# Run a new container with the updated image
echo "🚀 Starting a new container..."
docker run -d -p 8080:8080 --name $CONTAINER_NAME $IMAGE_NAME || { echo "❌ Docker run failed!"; exit 1; }

# Restore the live Nginx config
echo "🔄 Restoring live site..."
sudo unlink "$LIVE_CONF"
sudo ln -sf /etc/nginx/sites-available/cwrm.wasca.in "$LIVE_CONF"
sudo nginx -s reload
echo "✅ Live site restored."

echo "🎉 Server update complete!"
