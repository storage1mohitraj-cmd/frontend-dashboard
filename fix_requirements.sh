#!/bin/bash
cd /home/opc/app/bot
sed -i 's/wavelink>=3.4.1/wavelink>=1.3.5,<2.0.0/' requirements.txt
echo "Fixed wavelink version in requirements.txt"