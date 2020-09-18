from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gi
import cairo
import argparse

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, GLib

import pytz
from datetime import datetime, timedelta, date

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class ScheduleWindow(Gtk.Window):
    def __init__(self, args):
        super(ScheduleWindow, self).__init__(title='schedule')
        self.args = args

        self.cst = pytz.timezone('America/Chicago')

        self.inc_pixels = 20
        self.inc = timedelta(minutes=15)

        self.background = Gtk.Fixed()

        self.fixed = Gtk.Fixed()
        self.draw = Gtk.DrawingArea()
        self.draw.set_size_request(400, self.inc_pixels*24)
        self.draw.connect('draw', self.draw_expose)
        
        # self.add(self.fixed)
        self.background.add(self.fixed)
        self.background.add(self.draw)
        self.add(self.background)
        # self.add(self.draw)
        

        self.on_timeout(None)
        self.timeout_id = GLib.timeout_add_seconds(5, self.on_timeout, None)

        # self.show_all()

    def draw_expose(self, area, context):
        w = area.get_allocated_width()
        h = area.get_allocated_height()

        context.set_source_rgba(0,0,0,0)
        context.rectangle(0, 0, w, h)
        context.fill()

        now = datetime.now().astimezone(self.cst)           
        s=int((now - self.start_date) / self.inc)

        print(s * self.inc_pixels)

        context.set_source_rgba(1, 1, 1, 0.5)
        context.set_line_width(5)
        context.move_to(0, s*self.inc_pixels)
        context.line_to(w, s * self.inc_pixels)
        # context.set_source_rgba(1,1,1,1)
        context.stroke()


    def on_timeout(self, user_data):
        now = datetime.now()
        self.start_date = datetime(now.year, now.month, now.day, 7, 30, 0, tzinfo=self.cst)
        
        self.render_events()

        self.draw.queue_draw()

    def render_events(self):
        comps = [c for c in self.fixed]
        for c in comps:
            self.fixed.remove(c)
            c.destroy()

        events = get_events(self.args.calendar_id, self.cst)

        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))

            print(start, end)

            s = int((datetime.fromisoformat(start) - self.start_date) / self.inc)

            increments = (datetime.fromisoformat(end) - datetime.fromisoformat(start)) 
            increments = int(increments / self.inc)

            print(increments)

            summary = Gtk.Label()
            summary.set_alignment(0, 0)
            summary.set_justify(Gtk.Justification.LEFT)
            # summary.set_css_name('event')
            summary.set_text(event['summary'])
            summary.set_size_request(400, self.inc_pixels*increments - 10)

            self.fixed.put(summary, 0, s * self.inc_pixels)
            
            # self.grid.attach(summary, 0, i, 1, increments)
            # i += increments

            # print(i)

        self.fixed.show_all()




def main(args):
    get_styles()
    window = ScheduleWindow(args)
    window.set_app_paintable(True)
    window.set_decorated(False)
    window.set_visual(window.get_screen().get_rgba_visual())
    
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    
    if not args.geometry is None:
        if not window.parse_geometry(args.geometry):
            print('geometry "{}" not parsed.')

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    print('shutting down')

def get_styles():
    css = b"""
    label { 
        font-size: 15px;
        font-family: Carlito; 
        color: white;
        text-shadow: grey;
        background-color: #8811ff;
        border-radius: 10px;
        padding: 10px;

    }
    GtkLayout {
       background-color: transparent;
    }

    /*
    GtkViewport {
        background-color: transparent;
    }
    */
    """

    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(css)

    context = Gtk.StyleContext()
    screen = Gdk.Screen.get_default()

    context.add_provider_for_screen(
        screen,
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def get_events(calendar_id, tzinfo):
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    today = date.today()
    midnight = datetime.combine(today, datetime.min.time())
    
    midnight = tzinfo.localize(midnight)

    utc = pytz.UTC
    midnightUTC = midnight.astimezone(utc).isoformat() #.strftime('%Y-%m-%dT%H') + 'Z'
    tomorrowUTC = (midnight + timedelta(1)).astimezone(utc).isoformat()
    now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time

    print(now, midnightUTC)
    
    events_result = service.events().list(calendarId=calendar_id, timeMin=midnightUTC, timeMax=tomorrowUTC,
                                        maxResults=20, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        # print(start, event['summary'], event['location'])
        loc = ''
        try:
            loc = event['location']
        except KeyError:
            pass

        print(start, event['summary'], loc)

    return events


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--calendar_id', type=str)
    parser.add_argument("--geometry", help="window geometry")

    main(parser.parse_args())