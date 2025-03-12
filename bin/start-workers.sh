
sudo systemctl start rqworker-fetch@1
sudo systemctl start rqworker-fetch@2
sudo systemctl start rqworker-fetch@3

sudo systemctl start rqworker-post

sudo systemctl start rqworker-mailbox

# sudo journalctl -u rqworker-fetch@1 -f
