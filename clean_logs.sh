#!/usr/bin/env bash
####clean logs
list=`find  /var/log/* `
for path in $list ; do
if [ -f ${path} ]
then
echo ${path}  - resize to zero
echo '' > ${path}; fi  done
#######
