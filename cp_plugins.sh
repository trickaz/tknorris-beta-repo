#!/bin/sh

#rsync --delete -av --exclude=".*" --exclude="*.pyc" ~/eclipseworkspace/1Channel/ ~/eclipseworkspace/tknorris-beta-repo/plugin.video.1channel
rsync --delete -av --exclude=".*" --exclude="*.pyc" ~/eclipseworkspace/salts/ ~/eclipseworkspace/tknorris-beta-repo/plugin.video.salts
rsync --delete -av --exclude=".*" --exclude="*.pyc" ~/eclipseworkspace/1channel.themepaks/ ~/eclipseworkspace/tknorris-beta-repo/script.1channel.themepak
