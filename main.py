import os
import glob
from replit import db
from flask import Flask, request

import smtplib
from jinja2 import Environment, FileSystemLoader
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email import encoders
from email.mime.base import MIMEBase

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, user, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.callbackquery import CallbackQuery
from telegram.ext import Dispatcher, CallbackContext, CallbackQueryHandler, CommandHandler, MessageHandler, ConversationHandler, Filters
from telegram.ext.filters import MessageFilter

# APP PARAMS
BOT_TOKEN = os.getenv("BOT_TOKEN")
URL = "https://rh-finance-bot.charleslimjh.repl.co/"
EMAIL_ADDRESS = os.getenv('MAIL_USER')
EMAIL_PASSWORD = os.getenv('MAIL_PW')

# CONSTANTS
INVALID_COMMAND = "Sorry, I didn't understand what you just said. Please enter a valid command"
BUYEE_NAME_PROMPT = "Please enter the buyer's name, or type 'ok' to continue:"
BUYEE_MATRIC_PROMPT = "Please enter the buyer's matric card number:"
BUYEE_CCA_PROMPT = "Please enter the CCA:"
BUYEE_EVENT_PROMPT = "Please enter the event name:"
NUM_RECEIPTS_PROMPT = "Please enter the number of receipts: "
RECEIPT_TYPE_PROMPT = "Please choose your receipt type:"
RECEIPT_DETAILS_PROMPT = "Enter the details of this receipt in the following format: (AMOUNT,VENDOR,PURPOSE,DATE)"
RECEIPT_IMAGE_PROMPT = "Upload a clear image of the receipt:"
SUPPLEMENTARY_DOCS_PROMPT = "Please upload any supporting documents (e.g. Bank statements, Prize lists, Currency exchange etc.) one at a time, then type 'ok' to continue."
BUDGET_CATEGORY_PROMPT = "Please enter the Budget Category:"
CONFIRMATION_PROMPT = "Alright, all received! Please confirm that all the information you entered is true"
CANCEL_SETUP_PROMPT = "Goodbye, see you next time!"
SETUP_NEW_USER = """You have not saved your information yet, Treasurer!
Please input in your full name, phone number and email, separated by commas.
For example, type in 'Charles Lim,98765432,charleslimjh@gmail.com'."""
SETUP_EXISTING_USER = """To update your particulars, input in your full name, phone number and email, separated by commas. Else, type /cancel.

For example, type in 'Charles Lim,98765432,charleslimjh@gmail.com'."""

UPDATE_USER = range(0)
BUYEE_NAME, BUYEE_MATRIC, BUYEE_CCA, BUYEE_EVENT, NUM_RECEIPTS, RECEIPT_TYPE, RECEIPT_DETAILS, RECEIPT_IMAGE, SUPPLEMENTARY_DOCS, BUDGET_CATEGORY, CONFIRMATION = range(
  11)

# utils
num_images = 0
supp_images = 0

def listfiles(path):
    for file in os.listdir(path):
        if os.path.isfile(os.path.join(path, file)):
            yield file

def clear_folder(folder_name):
  for f in listfiles(folder_name):
    os.remove("./images/" + f)

def attach_docs(folder_name, msg):
  
  for f in listfiles(folder_name):
      part = MIMEBase('application', "octet-stream")
      part.set_payload(open("./images/" + f, "rb").read())
      encoders.encode_base64(part)
      part.add_header('Content-Disposition', 'attachment', filename=f)
      msg.attach(part)
  return msg
    
# Initialize flask app and bot
app = Flask(__name__)
bot = Bot(BOT_TOKEN)


def send_email(data):
  environment = Environment(loader=FileSystemLoader("templates/"))
  template = environment.get_template("template.html")
  content = template.render(data)

  msg = MIMEMultipart()
  msg['Subject'] = data["CCA"] + ' Claims - ' + data["Event"]
  msg['From'] = EMAIL_ADDRESS
  msg['To'] = data["TreasurerEmail"]
  msg.attach(MIMEText(content, 'html'))

  print("attaching files")
  msg = attach_docs("./images", msg)

  with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    smtp.send_message(msg)


#################################
### Command Handler Functions ###
#################################


def start(update, context):
  update.message.reply_text(
    "Welcome to the RH Finance Bot, helping RH Treasurers process your claims!"
  )


def userSetup(update, context):
  # new user
  chat_id = str(update.message.chat.id)
  print("Existing user:", str(chat_id) in list(db.keys()))

  if not str(chat_id) in list(db.keys()):
    print("record user info")
    update.message.reply_text(SETUP_NEW_USER)
    return UPDATE_USER

  # existing user
  else:
    print("display user info")
    userInfo = db[str(chat_id)].split(',')
    print(db[str(chat_id)], "\n", userInfo)
    userName = userInfo[0]
    userPhone = userInfo[1]
    userEmail = userInfo[2]
    update.message.reply_text(
      "Treasurer Name: {}\nTreasurer Phone: {}\nEmail:{}".format(
        userName, userPhone, userEmail))
    update.message.reply_text(SETUP_EXISTING_USER)
    return UPDATE_USER


def updateUser(update, context):
  print("updating user particulars")
  data = update.message.text.strip()
  db[str(update.message.chat.id)] = data
  data = data.split(',')
  context.user_data["TreasurerName"] = data[0]
  context.user_data["TreasurerPhone"] = data[1]
  context.user_data["TreasurerEmail"] = data[2]

  update.message.reply_text("""Okay, particulars updated as follows:
  Treasurer name: {}
  Phone number: {}
  Email: {}""".format(data[0], data[1], data[2]))

  return ConversationHandler.END


def cancelSetup(update, context):
  print("cancel setup process")
  update.message.reply_text("Okay, cancelling setup operation!",
                            reply_markup=ReplyKeyboardRemove())
  return ConversationHandler.END


#################################
### Receipt Handler Functions ###
#################################


def online_receipt(update, context):
  clear_folder("./images")
  num_images = 0
  supp_images = 0
  print("get authorisation letter names", "\n")
  context.user_data['Students'] = []

  update.message.reply_text(BUYEE_NAME_PROMPT)
  return BUYEE_NAME


def buyee_name(update, context):
  print("get authorisation letter matric numbers")
  print(context.user_data, "\n")

  text = str(update.message.text)
  if text.lower() == 'ok':
    update.message.reply_text(BUYEE_CCA_PROMPT)
    return BUYEE_CCA
  
  context.user_data['Students'].append(text)
  update.message.reply_text(BUYEE_MATRIC_PROMPT)
  return BUYEE_MATRIC


def buyee_matric(update, context):
  print("ask for cca/next authorisation letter name")
  print(context.user_data, "\n")

  text = str(update.message.text)

  # add name/matric pair
  name = context.user_data['Students'].pop()
  context.user_data['Students'].append({"name": name, "matric": text})
  update.message.reply_text(BUYEE_NAME_PROMPT)
  return BUYEE_NAME


def buyee_cca(update, context):
  print("ask for event")
  print(context.user_data, "\n")

  text = str(update.message.text)
  context.user_data['CCA'] = text
  update.message.reply_text(BUYEE_EVENT_PROMPT)
  return BUYEE_EVENT


def buyee_event(update, context):
  print("ask for number of receipts")
  print(context.user_data, "\n")

  text = str(update.message.text)
  context.user_data['Event'] = text
  update.message.reply_text(NUM_RECEIPTS_PROMPT)
  return NUM_RECEIPTS


def num_receipts(update, context):
  print("ask for receipt type")
  print(context.user_data, "\n")

  text = int(update.message.text)
  context.user_data['TotalReceipts'] = text
  reply_keyboard = [["Online", "Physical"]]
  update.message.reply_text(RECEIPT_TYPE_PROMPT,
                            reply_markup=ReplyKeyboardMarkup(
                              reply_keyboard, one_time_keyboard=True))
  return RECEIPT_TYPE


def receipt_type(update, context):
  print("ask for receipt details")
  print(context.user_data, "\n")

  text = str(update.message.text)
  if (text in context.user_data):
    context.user_data[text] += 1
  else:
    context.user_data[text] = 1

  update.message.reply_text(RECEIPT_DETAILS_PROMPT,
                            reply_markup=ReplyKeyboardRemove())
  return RECEIPT_DETAILS


def receipt_details(update, context):
  print("ask for receipt photo")
  print(context.user_data, "\n")

  text = str(update.message.text)
  if ('Receipts' in context.user_data):
    context.user_data['Receipts'].append(text)
  else:
    context.user_data['Receipts'] = [text]
  update.message.reply_text(RECEIPT_IMAGE_PROMPT)
  return RECEIPT_IMAGE


def receipt_image(update, context):
  print("ask for more receipts/supplementary docs")
  print(context.user_data, "\n")

  global num_images
  num_images += 1
  photo_file = update.message.photo[-1].get_file()
  photo_file.download("images/user_photo{}.jpg".format(num_images))
  user_data = context.user_data
  if ("TotalReceipts" in user_data and user_data["TotalReceipts"] > 1):
    user_data["TotalReceipts"] = user_data["TotalReceipts"] - 1
    reply_keyboard = [["Online", "Physical"]]
    update.message.reply_text(RECEIPT_TYPE_PROMPT,
                              reply_markup=ReplyKeyboardMarkup(
                                reply_keyboard, one_time_keyboard=True))
    return RECEIPT_TYPE
  else:
    update.message.reply_text(SUPPLEMENTARY_DOCS_PROMPT)
    return SUPPLEMENTARY_DOCS


def supplementary_docs(update, context):
  print("ask for more docs/budget category")
  print(context.user_data, "\n")

  global supp_images
  supp_images += 1
  try:
    photo_file = update.message.photo[-1].get_file()

  except:
    text = str(update.message.text)
    if text.lower() == 'ok':
      update.message.reply_text(BUDGET_CATEGORY_PROMPT)
      return BUDGET_CATEGORY
    update.message.reply_text(SUPPLEMENTARY_DOCS_PROMPT)
    return SUPPLEMENTARY_DOCS

  else:
    photo_file.download("images/supp_docs_photo{}.jpg".format(supp_images))
    update.message.reply_text(SUPPLEMENTARY_DOCS_PROMPT)
    return SUPPLEMENTARY_DOCS


def budget_category(update, context):
  print("ask for confirmation")
  print(context.user_data, "\n")

  text = str(update.message.text)
  context.user_data['BudgetCategory'] = text
  reply_keyboard = [["Confirm"]]
  update.message.reply_text(CONFIRMATION_PROMPT,
                            reply_markup=ReplyKeyboardMarkup(
                              reply_keyboard, one_time_keyboard=True))
  return CONFIRMATION


def confirmation(update, context):
  print("print summary")
  print(context.user_data, "\n")

  # process data
  user_data = context.user_data
  if not "TreasurerEmail" in context.user_data:
    print(db[str(update.message.chat.id)])
    tmp = db[str(update.message.chat.id)].split(',')
    context.user_data["TreasurerName"] = tmp[0]
    context.user_data["TreasurerPhone"] = tmp[1]
    context.user_data["TreasurerEmail"] = tmp[2]
  
  if not ("Physical" in user_data):
    context.user_data["Physical"] = 0

  if not ("Online" in user_data):
    context.user_data["Online"] = 0

  totalPrice = 0
  tmp = []
  for receipt in context.user_data["Receipts"]:
    receipt = receipt.split(",")
    tmp.append({
      "count": str(len(tmp) + 1),
      "amount": receipt[0],
      "vendor": receipt[1],
      "purpose": receipt[2],
      "date": receipt[3]
    })
    totalPrice += float(receipt[0])

  context.user_data["Receipts"] = tmp
  context.user_data["TotalAmount"] = totalPrice

  send_email(context.user_data)
  clear_folder("./images")

  reply_text = ""
  user_data = context.user_data
  for key in user_data:
    reply_text = reply_text + "{}: {}\n".format(key, user_data[key])
  update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())

  return ConversationHandler.END


def cancel(update, context):
  update.message.reply_text(CANCEL_SETUP_PROMPT,
                            reply_markup=ReplyKeyboardRemove())
  return ConversationHandler.END


def invalid(update, context):
  update.message.reply_text("Invalid input!")


################
### Handlers ###
################

online_receipt_handler = ConversationHandler(
  entry_points=[CommandHandler("onlinereceipt", online_receipt)],
  states={
    BUYEE_NAME: [MessageHandler(Filters.text & ~Filters.command, buyee_name)],
    BUYEE_MATRIC:
    [MessageHandler(Filters.text & ~Filters.command, buyee_matric)],
    BUYEE_CCA: [MessageHandler(Filters.text & ~Filters.command, buyee_cca)],
    BUYEE_EVENT:
    [MessageHandler(Filters.text & ~Filters.command, buyee_event)],
    NUM_RECEIPTS:
    [MessageHandler(Filters.text & ~Filters.command, num_receipts)],
    RECEIPT_TYPE:
    [MessageHandler(Filters.regex('^(Online|Physical)$'), receipt_type)],
    RECEIPT_DETAILS:
    [MessageHandler(Filters.text & ~Filters.command, receipt_details)],
    RECEIPT_IMAGE: [MessageHandler(Filters.photo, receipt_image)],
    SUPPLEMENTARY_DOCS:
    [MessageHandler(Filters.photo | Filters.text, supplementary_docs)],
    BUDGET_CATEGORY: [MessageHandler(Filters.text, budget_category)],
    CONFIRMATION: [MessageHandler(Filters.regex('^(Confirm)$'), confirmation)],
  },
  fallbacks=[CommandHandler("cancel", cancel)])

userSetupHandler = ConversationHandler(
  entry_points=[CommandHandler("setup", userSetup)],
  states={
    UPDATE_USER: [MessageHandler(Filters.text & ~Filters.command, updateUser)]
  },
  fallbacks=[CommandHandler("cancel", cancelSetup)])

## Set up dispatcher object ##

dispatcher = Dispatcher(bot, None)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(online_receipt_handler)
dispatcher.add_handler(userSetupHandler)

#######################################


@app.route('/{}'.format(BOT_TOKEN), methods=['POST'])
def respond():
  # retrieve the message in JSON and then transform it to Telegram object
  update = Update.de_json(request.get_json(force=True), bot)
  print(update.message.chat.id, update.message.chat.username,
        update.message.text)
  dispatcher.process_update(update)
  return "ok"


@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
  s = bot.setWebhook('{URL}{HOOK}'.format(URL=URL, HOOK=BOT_TOKEN))
  if s:
    return "webhook setup ok"
  else:
    return "webhook setup failed"


# homepage


@app.route('/')
def index():
  return 'App is live!'


# gunicorn --bind 0.0.0.0:5003 main:app
