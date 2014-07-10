#!/bin/sh

rsync --delete -av --exclude=".*" --exclude="*.pyc" ~/eclipseworkspace/1Channel/ ~/eclipseworkspace/tknorris-beta-repo/plugin.video.1channel
