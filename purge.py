# script to remove all entries in replit db
from replit import db

for key in list(db.keys()):
  del db[key]
