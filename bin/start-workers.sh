
sudo systemctl start rqworker-fetch@1
sudo systemctl start rqworker-fetch@2
sudo systemctl start rqworker-fetch@3

sudo systemctl start rqworker-post@1

# sudo journalctl -u rqworker-fetch@1 -f
