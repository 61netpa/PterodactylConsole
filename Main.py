import os;
import json;
import time;
import requests;
import threading;
import re;
import uuid;
from websocket import create_connection, WebSocketException;
import dearpygui.dearpygui as UI;

class UIFunctionsClass:
    def __init__(self):
        self.Options: dict[str | int, str | int] = {}

    def AddToggle(self, Parent: str, Tag: str, Label: str) -> str | None:
        if (not Tag or Tag in self.Options): return None;
        self.Options[Tag] = UI.add_checkbox(parent = Parent, tag = Tag, label = Label);
        return Tag;

    def AddSlider(self, Parent: str, Tag: str, Args: dict) -> str | None:
        if (not Tag or Tag in self.Options): return None;
        self.Options[Tag] = UI.add_slider_int(parent = Parent, tag = Tag, **Args);
        return Tag;

    def AddInputString(self, Parent: str, Tag: str, Args: dict) -> str | None:
        if (not Tag or Tag in self.Options): return None;
        self.Options[Tag] = UI.add_input_text(parent = Parent, tag = Tag, **Args);
        return Tag;

    def AddButton(self, Parent: str, Args: dict) -> str:
        return UI.add_button(parent = Parent, **Args);

    def AddLabel(self, Parent: str, Tag: str, Label: str, Args: dict = {}) -> str | None:
        if (not Tag or Tag in self.Options): return None;
        self.Options[Tag] = UI.add_text(parent = Parent, tag = Tag, default_value = Label, **Args);
        return Tag;

    def AddDropdown(self, Parent: str, Tag: str, Args: dict) -> str | None:
        if (Tag in self.Options): return None;
        self.Options[Tag] = UI.add_combo(parent = Parent, tag = Tag, **Args);
        return self.Options[Tag];

    def AddDivider(self, Parent: str):
        return UI.add_separator(parent = Parent);

    def GetValue(self, Tag: str) -> str | int | None:
        if (not Tag or Tag not in self.Options): return None;
        return UI.get_value(Tag);

    def SetValue(self, Tag: str, Value: str | int) -> None:
        if (not Tag or Tag not in self.Options): return;
        UI.set_value(Tag, Value);

    def SetConfiguration(self, Tag: str, Args: dict) -> None:
        if (not Tag or Tag not in self.Options): return;
        UI.configure_item(Tag, **Args);

class Main:
    def __init__(self):
        self.Config = self.GetConfig();
        self.Connection = None;
        self.CurrentState = None;
        self.Window: dict = { "Dragging": False, "UpdateTime": time.time() };
        self.UIFunctions = UIFunctionsClass();
        self.LogBuffer = "Console Initialized.\n";
        self.AnsiRegex = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]');

    def GetConfig(self) -> dict:
        try:
            Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Config.json");
            if (os.path.exists(Path)):
                with open(Path) as File:
                    return json.load(File);
            return {};
        except Exception as Error:
            print(f"Couldn't get config. Error: {Error}");
            return {};

    def SetConfig(self) -> None:
        Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Config.json");
        PanelURL = self.UIFunctions.GetValue("PanelURL").removeprefix("https://").removeprefix("http://");
        ServerUUID = self.UIFunctions.GetValue("ServerUUID");
        APIKey = self.UIFunctions.GetValue("APIKey");
        if (PanelURL == "" or ServerUUID == " "): print("Panel URL can't be empty."); self.UIFunctions.SetValue("PanelURL", self.Config['PanelURL']); return;
        if (ServerUUID == "" or ServerUUID == " "): print("Server UUID can't be empty."); self.UIFunctions.SetValue("ServerUUID", self.Config['ServerUUID']); return;
        if (APIKey == "" or APIKey == " "): print("API Key can't be empty."); self.UIFunctions.SetValue("APIKey", self.Config['APIKey']); return;
        try:
            FormattedUUID = uuid.UUID(ServerUUID);
            if (str(FormattedUUID) != str(ServerUUID).lower()):
                print("Invalid UUID.");
                self.UIFunctions.SetValue("ServerUUID", self.Config['ServerUUID']);
                return;
        except ValueError:
            print("Invalid UUID.");
            self.UIFunctions.SetValue("ServerUUID", self.Config['ServerUUID']);
            return;
        if (not APIKey.lower().startswith("ptlc_")):
            print("Invalid API Key.");
            self.UIFunctions.SetValue("APIKey", self.Config['APIKey']);
            return;
        NewConfig = { "PanelURL": PanelURL, "ServerUUID": ServerUUID, "APIKey": APIKey };
        with open(Path, "w") as File:
            json.dump(NewConfig, File, indent = 4);
        self.Config = NewConfig;
        if (self.Connection):
            self.Connection.close();
            self.Connection = None;

    def SetWebsocket(self) -> bool:
        ResponseHeaders = {
            "Authorization": f"Bearer {self.Config['APIKey']}",
            "Accept": "application/json",
        };
        try:
            Response = requests.get(f"https://{self.Config['PanelURL']}/api/client/servers/{self.Config['ServerUUID']}/websocket", headers = ResponseHeaders, timeout = 10 );
            Response.raise_for_status();
            ResponseData = Response.json();
            if ("data" not in ResponseData or "token" not in ResponseData["data"] or "socket" not in ResponseData["data"]):
                print(f"Unexpected response from server. Raw response: {ResponseData}");
                return False;
            Data = Response.json()["data"];
            Token = Data["token"];
            WebsocketURL = Data["socket"];
        except (requests.exceptions.RequestException) as Error:
            print(f"An error occurred while sending the HTTP request to the panel. Is the API key wrong? Error: {Error}");
            return False;
        except (json.JSONDecodeError) as Error:
            print(f"Failed to parse the JSON. The server most likely returned a webpage or just an invalid json. Error: {Error}");
            return False;
        except (Exception) as Error:
            print(f"An error occurred while getting websocket data. Error: {Error}");
            return False;
        WebSocketHeaders = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        };
        try:
            self.Connection = create_connection(WebsocketURL, header = WebSocketHeaders, origin = f"https://{self.Config['PanelURL']}", timeout = 10);
            AuthPayload = json.dumps({"event": "auth", "args": [Token]});
            self.Connection.send(AuthPayload);
            print("Websocket has been successfully set and connected.");
            return True;
        except (Exception) as Error:
            print(f"An error occurred while connecting to the websocket. Error: {Error}");
            self.Connection = None;
            return False;

    def SendPowerCommand(self, Command: str) -> None:
        EndpointURL = f"https://{self.Config['PanelURL']}/api/client/servers/{self.Config['ServerUUID']}/power";
        Headers = {
            "Authorization": f"Bearer {self.Config['APIKey']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        };
        try:
            requests.post(EndpointURL, headers = Headers, json = { "signal": Command }, timeout = 10);
        except (Exception) as Error:
            print(f"An error has occurred while sending the power command. Error: {Error}");

    def SendConsoleCommand(self) -> None:
        Command = self.UIFunctions.GetValue("InputBar");
        if (Command == ""): return;
        EndpointURL = f"https://{self.Config['PanelURL']}/api/client/servers/{self.Config['ServerUUID']}/command";
        Headers = {
            "Authorization": f"Bearer {self.Config['APIKey']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        };
        self.UIFunctions.SetValue("InputBar", "");
        try:
            requests.post(EndpointURL, headers = Headers, json = { "command": Command }, timeout = 10);
        except (Exception) as Error:
            print(f"An error has occurred while sending the console command. Error: {Error}");

    def HideCredentials(self, Sender, AppData, UserData) -> None:
        self.UIFunctions.SetConfiguration(AppData, { "password": True });
        pass;

    def ShowCredentials(self, Sender, AppData, UserData) -> None:
        self.UIFunctions.SetConfiguration(AppData, { "password": False });
        pass;

    @staticmethod
    def OnExit() -> None:
        UI.destroy_context();

    def BuildUI(self) -> None:
        UI.create_context();
        Viewport = UI.create_viewport(title = "Console", width = 630, height = 710, decorated = False, resizable = False);
        UI.setup_dearpygui();
        UI.show_viewport();
        with UI.window(label = "Console", tag = "MainWindow", width = 630, height = 710, no_title_bar = False, no_resize = True, no_move = True, no_collapse = True, no_scroll_with_mouse = True, no_scrollbar = True, on_close = self.OnExit):
            with UI.child_window(tag = "OutputConsole", height = -160):
                self.UIFunctions.AddLabel("OutputConsole", "ConsoleBuffer", self.LogBuffer);
            with UI.group(tag = "ServerCommandBar", horizontal = True):
                self.UIFunctions.AddInputString("ServerCommandBar", "InputBar", { "hint": "Enter command here...", "width": -148, "on_enter": True, "callback": self.SendConsoleCommand });
                self.UIFunctions.AddButton("ServerCommandBar", { "width": 140, "label": "Send", "callback": self.SendConsoleCommand });
            with UI.group(tag = "ServerStatusGroup", horizontal = True):
                self.UIFunctions.AddLabel("ServerStatusGroup", "ServerStatusTitle", "Server Status:");
                self.UIFunctions.AddLabel("ServerStatusGroup", "ServerStatus", "Offline", { "color": (255, 50, 50) });
            self.UIFunctions.AddLabel("MainWindow", "ServerStats", "CPU: 0.00%  Memory: 0.00GB/8.00GB");
            with UI.group(tag = "ServerPowerButtons", horizontal = True):
                self.UIFunctions.AddButton("ServerPowerButtons", { "width": 147, "label": "Start", "callback": lambda: self.SendPowerCommand("start") });
                self.UIFunctions.AddButton("ServerPowerButtons", { "width": 147, "label": "Restart", "callback": lambda: self.SendPowerCommand("restart") });
                self.UIFunctions.AddButton("ServerPowerButtons", { "width": 147, "label": "Stop", "callback": lambda: self.SendPowerCommand("stop") });
                self.UIFunctions.AddButton("ServerPowerButtons", { "width": 147, "label": "Force Kill", "callback": lambda: self.SendPowerCommand("kill") });
            self.UIFunctions.AddInputString("MainWindow", "PanelURL", { "label": "Panel URL", "hint": "Enter your panel URL here...", "default_value": self.Config['PanelURL'], "width": 500, "on_enter": True, "password": True, "callback": self.SetConfig });
            self.UIFunctions.AddInputString("MainWindow", "ServerUUID", { "label": "Server UUID", "hint": "Enter your server UUID here...", "default_value": self.Config['ServerUUID'], "width": 500, "on_enter": True, "password": True, "callback": self.SetConfig });
            self.UIFunctions.AddInputString("MainWindow", "APIKey", { "label": "API Key", "hint": "Enter your API key here...", "default_value": self.Config['APIKey'], "width": 500, "on_enter": True, "password": True, "callback": self.SetConfig });
            with UI.item_handler_registry(tag = "SecretInputRegistry"):
                UI.add_item_activated_handler(callback = self.ShowCredentials);
                UI.add_item_deactivated_handler(callback = self.HideCredentials);
            UI.bind_item_handler_registry("PanelURL", "SecretInputRegistry");
            UI.bind_item_handler_registry("ServerUUID", "SecretInputRegistry");
            UI.bind_item_handler_registry("APIKey", "SecretInputRegistry");

            def CheckDrag(_, Data: dict) -> None:
                if (UI.is_mouse_button_down(0)):
                    Y = Data[1];
                    if (-2 <= Y <= 19 and not self.Window["Dragging"]):
                        self.Window["Dragging"] = True;
                else:
                    self.Window["Dragging"] = False;

            def Drag(_, Data: dict) -> None:
                if (self.Window["Dragging"]):
                    Current = time.time();
                    CalculatedTime = Current - self.Window["UpdateTime"];
                    if (CalculatedTime >= 0):
                        Position = UI.get_viewport_pos();
                        X = Data[1];
                        Y = Data[2];
                        TargetX = Position[0] + X;
                        TargetY = Position[1] + Y;
                        DeltaX = (TargetX - Position[0]) * 0.25;
                        DeltaY = (TargetY - Position[1]) * 0.25;
                        FinalX = Position[0] + DeltaX;
                        FinalY = Position[1] + DeltaY;
                        UI.configure_viewport(Viewport, x_pos = FinalX, y_pos = FinalY);
                        self.Window["UpdateTime"] = Current;

            with UI.handler_registry():
                UI.add_mouse_drag_handler(0, callback = Drag);
                UI.add_mouse_move_handler(callback = CheckDrag);

    def WebsocketWorker(self):
        self.SetWebsocket();
        ConnectionStartTime = time.time();
        while (True):
            if (self.Connection and (time.time() - ConnectionStartTime) > 600):
                print("Websocket is about to die :sob:. Refreshing...");
                self.Connection.close();
                self.Connection = None;
                self.SetWebsocket();
                ConnectionStartTime = time.time();
                continue;
            if (not self.Connection):
                if (not self.SetWebsocket()):
                    time.sleep(1);
                    continue;
            else:
                try:
                    Message = self.Connection.recv();
                    Data = json.loads(Message);
                    EventType = Data["event"];
                    match EventType:
                        case "status":
                            self.CurrentState = Data.get("args")[0];
                            if (self.CurrentState == "offline"):
                                self.UIFunctions.SetValue("ServerStatus", "Offline");
                                self.UIFunctions.SetConfiguration("ServerStatus", { "color": (255, 50, 50) });
                            elif (self.CurrentState == "stopping"):
                                self.UIFunctions.SetValue("ServerStatus", "Stopping");
                                self.UIFunctions.SetConfiguration("ServerStatus", { "color": (255, 50, 50) });
                            elif (self.CurrentState == "starting"):
                                self.UIFunctions.SetValue("ServerStatus", "Starting");
                                self.UIFunctions.SetConfiguration("ServerStatus", { "color": (255, 150, 0) });
                            elif (self.CurrentState == "running"):
                                self.UIFunctions.SetValue("ServerStatus", "Online");
                                self.UIFunctions.SetConfiguration("ServerStatus", { "color": (50, 255, 50) });
                        case "stats":
                            StatsString = Data.get("args", ["{}"])[0];
                            Stats = json.loads(StatsString);
                            CPUUsage = Stats.get("cpu_absolute", 0.0);
                            RamUsage = Stats.get("memory_bytes", 0);
                            RamLimit = Stats.get("memory_limit_bytes", 0);
                            GBDivisor = 1024 ** 3;
                            RamUsageGB = RamUsage / GBDivisor;
                            RamLimitGB = RamLimit / GBDivisor;
                            self.UIFunctions.SetValue("ServerStats", f"CPU: {CPUUsage:.2f}%  Memory: {RamUsageGB:.2f}GB/{RamLimitGB:.2f}GB");
                        case "console output":
                            RawOutputString = Data.get("args", [""])[0];
                            CleanOutputString = self.AnsiRegex.sub('', RawOutputString);
                            self.LogBuffer += CleanOutputString + "\n";
                            self.UIFunctions.SetValue("ConsoleBuffer", self.LogBuffer);
                            UI.set_y_scroll("OutputConsole", UI.get_y_scroll_max("OutputConsole") + 100);
                except (WebSocketException) as Error:
                    print(f"Websocket connection lost, Error: {Error}");
                    self.Connection = None;
                except (json.JSONDecodeError):
                    pass;
                except (Exception) as Error:
                    print(f"An error has occured. Error: {Error}");
                    self.Connection = None;
                    time.sleep(5);

    def Run(self):
        self.BuildUI();
        threading.Thread(target = self.WebsocketWorker, daemon = True).start();
        UI.start_dearpygui();

if (__name__ == "__main__"):
    Main().Run();
