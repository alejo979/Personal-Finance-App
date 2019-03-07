# import tkinter
import datetime
import pytz
import sqlite3
import locale

db = sqlite3.connect("main_database.sqlite", detect_types=sqlite3.PARSE_DECLTYPES)
db.execute("CREATE TABLE IF NOT EXISTS accounts (name TEXT PRIMARY KEY NOT NULL, currency TEXT NOT NULL, card_bal INTEGER NOT NULL,"
           " cash_bal INTEGER NOT NULL)")
db.execute("CREATE TABLE IF NOT EXISTS history (time TIMESTAMP NOT NULL,"
           " account TEXT NOT NULL, amount INTEGER NOT NULL, category TEXT NOT NULL,"
           " bal_type TEXT NOT NULL, subcateg TEXT NOT NULL, comment TEXT, PRIMARY KEY (time, account))")


class Account(object):

    @staticmethod
    def _current_time():
        return pytz.utc.localize(datetime.datetime.utcnow())
        # return datetime.datetime(2018, 11, 18, 10, 25, 42)

    @staticmethod
    def retrieve_account(name):
        cursor = db.execute("SELECT name, currency, card_bal, cash_bal FROM accounts WHERE (name = ?)", (name,))
        one_row = cursor.fetchone()
        return one_row

    def display_all_transac(self):
        cursor = db.execute("SELECT strftime('%Y-%m-%d %H:%M:%S', history.time, 'localtime') AS localtime,"
                            " history.account, history.category, history.amount, history.bal_type, history.subcateg, "
                            " history.comment FROM history WHERE (account = ?) ORDER BY history.account, history.time", (self.name,))
        all_transac = cursor.fetchall()
        for ROW in all_transac:
            print("\t".join([ROW[0], ROW[1], ROW[2], locale.currency(ROW[3]/100, grouping=True), ROW[4], ROW[5]]))
            # [str(i) for i in row_list]

    def __init__(self, name: str, currency: str, opening_card_balance: int = 0, opening_cash_balance: int = 0):
        data = Account.retrieve_account(name)
        if data:
            self.name, self.currency, self._card_bal, self._cash_bal = data
            self._balance = (self._card_bal/100) + (self._cash_bal/100)
            # print("An account with that name already exists:")
            locale.setlocale(locale.LC_ALL, self.currency)
            print("Retrieved record for {}. Total balance is {} (Card:{} + Cash:{})"
                  .format(self.name, locale.currency(self._balance, grouping=True),
                          locale.currency(self._card_bal/100, grouping=True),
                          locale.currency(self._cash_bal/100, grouping=True)))

        else:
            locale.setlocale(locale.LC_ALL, currency)
            self.name = name
            self._card_bal = opening_card_balance
            self._cash_bal = opening_cash_balance
            self._balance = (self._card_bal/100) + (self._cash_bal/100)
            cursor = db.execute("INSERT INTO accounts VALUES(?, ?, ?, ?)", (name, currency, opening_card_balance, opening_cash_balance))
            cursor.connection.commit()
            print("Account created for {}. Total balance is {} (Card:{:.2f} + Cash:{:.2f})"
                  .format(self.name, locale.currency(self._balance, grouping=True), self._card_bal/100, self._cash_bal/100))

    def show_balance(self):
        print("Total Balance on account {} is {} (Card:{} + Cash:{})".format(self.name,
                                                                             locale.currency(self._balance, grouping=True),
                                                                             locale.currency(self._card_bal/100, grouping=True),
                                                                             locale.currency(self._cash_bal/100, grouping=True)))
        print()

    def _save_update(self, amount, bal_type, subcateg, comment, category):
        if bal_type == 'card':
            new_card_balance = self._card_bal + amount
            self._balance = (new_card_balance/100) + (self._cash_bal/100)
            transact_time = Account._current_time()

            try:
                db.execute("UPDATE accounts SET card_bal = ? WHERE (name = ?)", (new_card_balance, self.name))
                db.execute("INSERT INTO history VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (transact_time, self.name, amount, category, bal_type, subcateg, comment))
            except sqlite3.Error:
                db.rollback()
            else:
                db.commit()
                self._card_bal = new_card_balance

        elif bal_type == 'cash':
            new_cash_balance = self._cash_bal + amount
            self._balance = (new_cash_balance/100) + (self._card_bal/100)
            transact_time = Account._current_time()

            try:
                db.execute("UPDATE accounts SET cash_bal = ? WHERE (name = ?)", (new_cash_balance, self.name))
                db.execute("INSERT INTO history VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (transact_time, self.name, amount, category, bal_type, subcateg, comment))
            except sqlite3.Error:
                db.rollback()
            else:
                db.commit()
                self._cash_bal = new_cash_balance

        else:
            print("Incorrect account type entered")

    def deposit(self, amount: int, bal_type, comment='', category='deposit', subcateg='') -> float:
        if bal_type == 'card':
            if amount > 0.0:
                self._save_update(amount, 'card', subcateg, comment, category)
                print("{:.2f} deposited to card".format(amount / 100))
            return self._card_bal / 100

        elif bal_type == 'cash':
            if amount > 0.0:
                self._save_update(amount, 'cash', subcateg, comment, category)
                print("{:.2f} deposited to cash".format(amount / 100))
            return self._cash_bal / 100

        self.show_balance()

    def expense(self, amount: int, bal_type, subcateg='', comment=''):
        category = 'expense'
        # if bal_type == 'card':
        if 0 < amount <= (self._card_bal if bal_type == 'card' else self._cash_bal):
            self._save_update(-amount, bal_type, subcateg, comment, category)
            print("{:.2f} deducted from {}".format(amount / 100, 'card' if bal_type == 'card' else 'cash'))
            self.show_balance()
            return amount / 100
        else:
            print("The amount must be greater than zero and no more than your account balance")
            return 0.0

    def transfer(self, amount: int, from_acc, to_acc):  # just internal transfer within same Account: Card to Cash
        if from_acc == 'card' and to_acc == 'cash':
            if 0 < amount <= self._card_bal:
                self._save_update(-amount, bal_type='card', subcateg='', comment='to cash', category='transfer')
                self._save_update(amount, bal_type='cash', subcateg='', comment='from card', category='transfer')
                print("{:.2f} transfered from card to cash".format(amount / 100))
                return amount / 100
            else:
                print("The amount must be greater than zero and no more than your account balance")
                return 0.0
        else:
            print("Other type of transfer attempted which is still not supported")
            return 0.0

    def display_filtered_transact(self):

        year_month_input = input('Type in the year and month (yyyy-mm): ')
        exp_inc_tran = input("Type in 'expense', or 'income' or 'transfer': ")

        cursor = db.execute("SELECT strftime('%Y-%m-%d %H:%M:%S', history.time, 'localtime') AS localtime,"
                            " history.account, history.category, history.amount, history.subcateg, history.comment FROM history"
                            " WHERE history.account = ? AND history.time LIKE ? AND history.category = ? ORDER BY history.account, history.time", (self.name, year_month_input+'%', exp_inc_tran))

        filt_trans = cursor.fetchall()
        if filt_trans and year_month_input != '' and exp_inc_tran != '':
            for line in filt_trans:
                print(line)
        else:
            print("There are no transactions for the specified month or type of transaction")


def print_main_menu():
    print("1. Create a new account\n2. Access an existing account\n3. Exit")


def submenu_quit_cont():
    return True if input("Do you want to continue (yes) or go out to main menu (no) ?: ") == 'yes' else False


if __name__ == '__main__':
    while True:
        print_main_menu()
        init_select = int(input(">> "))
        if init_select in [1, 2, 3]:
            if init_select == 1:
                input_name = input("Type in your first name: ")
                input_curr = input("Type in your currency: ")
                input_card = float(input("Type in opening card balance: "))
                input_cash = float(input("Type in opening cash balance: "))

                x = 1       # flow variable
                while x == 1:
                    confirmation = input("Are you sure you want to create an account for "
                                         "{} in {} currency, {} for Card Opening balance and {} for Cash Opening balance?: (Yes or No): "
                                         .format(input_name, input_curr, input_card, input_cash))

                    if confirmation in ['Yes', 'No']:
                        if confirmation == 'Yes':
                            new_acc = Account(input_name, input_curr, int(input_card * 100), int(input_cash * 100))
                            x = 0
                        else:
                            x = 0

                    else:
                        print("Please type in 'Yes' or 'No': ")

            elif init_select == 2:
                input_select_name = input("Please type in the name: ")
                row = Account.retrieve_account(input_select_name)
                if row:
                    existing_account = Account(input_select_name, '')
                    # print(locale.localeconv())
                    while True:

                        print("""
    1. View Current Balance (all accounts)
    2. Create a new Expense
    3. Create a new Income
    4. Create a transfer
    5. View filtered transactions
    6. View all transactions
    7. Cancel and Go Back to main menu\n""")

                        input_2 = int(input("Select an option (type in the number): "))

                        if input_2 == 1:
                            existing_account.show_balance()
                            print()
                            if submenu_quit_cont(): continue
                            else: break

                        elif input_2 == 2:
                            try:
                                exp_amount = int(float(input("Amount: "))*100)
                            except ValueError:
                                print("Please type in (.) dot before decimals")
                            else:
                                exp_bal_type = input("card or cash: ")
                                exp_subcateg = input("Expense category (Food, House, Health, Entertainment,etc.): ")
                                exp_comment = input("Comment (or just press Enter): ")
                                existing_account.expense(exp_amount, exp_bal_type, exp_subcateg, exp_comment)
                                if submenu_quit_cont(): continue
                                else: break

                        elif input_2 == 3:
                            try:
                                inc_amount = int(float(input("Amount: "))*100)
                            except ValueError:
                                print("Please type in (.) dot before decimals")
                            else:
                                inc_bal_type = input("card or cash: ")
                                inc_subcateg = input("Income category (Salary, Savings, Other, etc.): ")
                                inc_comment = input("Comment (or just press Enter): ")
                                existing_account.deposit(inc_amount, inc_bal_type, inc_comment, subcateg=inc_subcateg)
                                if submenu_quit_cont(): continue
                                else: break

                        elif input_2 == 4:
                            try:
                                transf_amount = int(float(input("Amount: "))*100)
                            except ValueError:
                                print("Please type in (.) dot before decimals and no thousand's separator")
                            else:
                                existing_account.transfer(transf_amount,'card','cash')
                                if submenu_quit_cont(): continue
                                else: break

                        elif input_2 == 5:
                            existing_account.display_filtered_transact()
                            if submenu_quit_cont(): continue
                            else: break

                        elif input_2 == 6:
                            existing_account.display_all_transac()
                            print()
                            if submenu_quit_cont(): continue
                            else: break

                        elif input_2 == 7:
                            break

                        else:
                            print("Type in just numbers from 1 to 6")

                else:
                    print("There is no account with that name, please check your spelling")

            else:   # if 3
                print("Goodbye!")
                break

        else:
            print("Please choose a valid option (1, 2 or 3)")

    db.close()
