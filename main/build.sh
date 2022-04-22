#!/usr/bin/env bash

set -e

echo "Creating working container"
container=`buildah from docker://python:3.9-alpine`

echo "Installing git and ssh on container"
buildah run $container apk update
buildah run $container apk add --no-cache git
buildah run $container apk add --no-cache openssh

echo "Copying src to container"
buildah copy $container main/src /src

echo "Installing python packages into container"
buildah run $container python3 -m pip install --upgrade pip
buildah run $container pip3 install --upgrade -r /src/requirements.txt

echo "Configuring container"
buildah config --entrypoint "python3 /src/entrypoint.py" $container
buildah config --author "Levi Lutz (contact.levilutz@gmail.com)" $container

echo "Building container to image"
buildah commit $container kube-ecr-cleanup-main

echo "Cleaning up"
buildah rm $container
