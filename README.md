### To run this project:

## first: 
pip install -r requirements.txt

## second:
Change the paths in .env for the paths in your pc

## then: 
python api.py

It will be listening on the topic 'procedimento' on kafka for the name listed on procedimentos.json

### To assure the proper work of the kafka consumer:

on server.properties -> Log Retention Policy, add/change this:

log.retention.ms=30000
log.retention.check.interval.ms=30000


