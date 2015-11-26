#!/usr/bin/python

import time
import configparser
import datetime

import tornado.ioloop
import tornado.web
import tornado.httpclient

import urllib
import json

from tornado.options import define, options, parse_command_line

define("port", default=8801, help="run on the given port", type=int)

main = None


class RSS2Pocket:

    config = None
    send_to_pocket_flag = True

    def send_to_pocket(self, my_data):

        import urllib.request
        import urllib.parse

        #
        # Don't do anything if in fake mode
        #

        if not self.send_to_pocket_flag:
            print("Not really sending to pocket, fake mode active")
            return True

        try:
            consumer_key = self.config["Pocket"]["consumer_key"]
            access_token = self.config["Pocket"]["access_token"]
        except:
            print("Cannot read Pocket data from config.ini")
            return False

        try:
            self.send_to_pocket_flag = self.config["Pocket"]["send_to_pocket"].lower() != "no"
        except:
            pass

        METHOD_URL = 'https://getpocket.com/v3/'
        REQUEST_HEADERS = { 'X-Accept': 'application/json' }

        params = {
            'consumer_key': consumer_key,
            'access_token': access_token,
            'actions': my_data
        }


        print(json.dumps(params))

        encoded = urllib.parse.urlencode(params).encode('utf-8')

        request = urllib.request.Request(METHOD_URL + "send", encoded, REQUEST_HEADERS)

        print(request.data)

        try:
            resp = urllib.request.urlopen(request)
            print(resp.read())
        except Exception as e:
            print(e)
            return False

        return True

    def get_from_pocket(self, handler, name, fake):

        import urllib.request
        import urllib.parse

        #
        # Don't do anything if in fake mode
        #

        try:
            self.send_to_pocket_flag = self.config["Pocket"]["send_to_pocket"].lower() != "no"
        except:
            pass

        if not self.send_to_pocket_flag:
            print("Not really sending to pocket, fake mode active")
            return True

        try:
            consumer_key = self.config["Pocket"]["consumer_key"]
            access_token = self.config["Pocket"]["access_token"]
        except:
            print("Cannot read Pocket data from config.ini")
            return False

        METHOD_URL = 'https://getpocket.com/v3/'
        REQUEST_HEADERS = { 'X-Accept': 'application/json' }

        params = {
            'tag'         : name,
            'detailType'  : "simple",
            'sort'        : "oldest",
            'state'       : "unread",
            'count'       : 100,
        }

        params["consumer_key"] = consumer_key
        params["access_token"] = access_token

        encoded = urllib.parse.urlencode(params).encode('utf-8')

        request = urllib.request.Request(METHOD_URL + "get", encoded, REQUEST_HEADERS)

        try:
            resp = urllib.request.urlopen(request)
            read_data = resp.read()
            decoded_data = read_data.decode('ascii')
            json_data = json.loads(decoded_data)
            formatted_data = json.dumps(json_data, indent=4)
            print(formatted_data)

            sorted_json_data = sorted(json_data["list"], key=lambda k: json_data["list"][k]["time_updated"])
            print("sorted:", sorted_json_data)

            for item in sorted_json_data:
                the_item = json_data["list"][item]
                handler.write('<input type="text" name="item_' + item + '" value="' + item + '" readonly="readonly"></input>')
                handler.write('<input type="checkbox" class="checkable" name="check_' + item + '" ></input>')
                handler.write(" - ")
                handler.write('<a href="' + the_item["resolved_url"] + '" target="' + item + '">link</a> - ')
                handler.write(datetime.datetime.fromtimestamp(int(the_item["time_updated"])).strftime('%Y-%m-%d %H:%M:%S'))
                handler.write(" - ")
                handler.write(the_item["resolved_title"] + "<br />")
                #handler.write(the_item["excerpt"] + "<br />")
                #handler.write("<br />")

        except Exception as e:
            print(e)
            return False

        return True

    def main(self, handler):
        self.config = configparser.ConfigParser()
        files = self.config.read("config.ini")
        if len(files) == 0:
            print("Could not read config file")
            exit(1)

        self.get_from_pocket(handler, "", False)


class ReadHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def add_arg(self, arg):
        result = ""
        if self.get_arguments(arg):
            result = "?" + arg + "=" + self.get_argument(arg)
        return result

    def post(self):
        action = self.get_argument("action")

        if action == "stop":
            self.set_header('Content-Type', 'text/html')
            self.write('<html><body><form name="f" action="read" method="post">')
            self.write(action + '<br />')
            self.write('<input type="submit" accesskey="r" value="Read" />')
            self.write('<input type="hidden" name="action" value="read" />')
            self.write("</form></body></html>")
            self.flush()
            self.finish()
            tornado.ioloop.IOLoop.instance().stop()
        elif action == "read":
            self.get()
        elif action == "archive":
            self.set_header('Content-Type', 'text/html')
            self.write('<html><body>')
            json_data = []
            arguments = self.request.arguments
            for argument in arguments:
                if "check_" in argument:
                    json_data.append({
                        "action":"archive",
                        "item_id":argument.replace("check_", ""),
                        "time":str(int(time.time()))
                    })
                    self.write(argument)
                    self.write(" - ")
                    self.write(self.get_argument(argument) + "<br />")

            self.write("archive! ")
            self.write(json.dumps(json_data))

            main.send_to_pocket(json.dumps(json_data))
            self.write('<form name="f" action="read" method="post">')
            self.write(action + '<br />')
            self.write('<input type="submit" accesskey="r" value="Read" />')
            self.write('<input type="hidden" name="action" value="read" />')
            self.write("</form></body></html>")
            self.flush()
            self.finish()

    def get(self):
        self.set_header('Content-Type', 'text/html; charset=utf-8')
        self.write('<html><head>')
        self.write('<script language="JavaScript">')
        self.write('function toggle(source) {checkboxes = document.getElementsByClassName("checkable");')
        self.write('for(var i=0, n=checkboxes.length;i<n;i++) {checkboxes[i].checked = source.checked;}')
        self.write('}')
        self.write('</script></head>')
        self.write('<body><form name="f" action="read" method="post">')

        self.write('<input type="checkbox" class="checkable" onClick="toggle(this)" /> Toggle All<br/>')
        main.main(self)

        self.write('<input type="submit" accesskey="q" value="Stop" /><br />')
        self.write('<input type="submit" accesskey="a" value="Archive" onclick="javascript:document.getElementById(\'id_action\').value=\'archive\'"/><br />')

        self.write('<input id="id_action" type="text" name="action" value="stop" />')


        self.write("</form></body></html>")

        self.flush()
        self.finish()


class GoHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def add_arg(self, arg):
        result = ""
        if self.get_arguments(arg):
            result = "?" + arg + "=" + self.get_argument(arg)
        return result

    def post(self):
        action = self.get_argument("action")
        self.write(action)

    def get(self):
        self.set_header('Content-Type', 'text/html')

        main.main(self)
        self.flush()
        self.finish()


class IndexHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        self.write("Hello!")
        self.finish()

if __name__ == "__main__":

    main = RSS2Pocket()

    app = tornado.web.Application([
        (r'/', IndexHandler),
        (r'/read', ReadHandler),
        (r'/go', GoHandler),
    ])

    parse_command_line()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


