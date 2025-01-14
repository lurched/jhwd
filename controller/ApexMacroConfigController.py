import os
import json
from enum import Enum
import traceback
from model.KeyBinding import KeyBinding
from model.KeyBindingTableModel import KeyBindingTableModel
from model.MacroFunction import MacroFunction

from model.ApexStatus import Status
from model.Settings import Settings
from view.widgets.ApexMacroConfigWidget import MacroEditDialog 
from view.widgets.ApexMacroConfigWidget import QMacroConfigWidget
tempdir = "C:/Users/Dip/AppData/Local/jhwd"

class AimMode(Enum):

    HOLD_MOUSE_BTN_2 = "HOLD"
    CLICK_MOUSE_BTN_2 = "CLICK"

class MacroMode(Enum):

    LGS = "LGS"
    GHUB = "GHUB"
    GHUB2 = "GHUB-通用鼠标"

class MacroConfigController():

    status = Status()

    config_files = {"config_file": (tempdir+"/config.lua").replace("\\","/"),
                "autorecognize_file": (tempdir+"/x.lua").replace("\\","/"),
                "weapon_file": (tempdir+"/weapon.lua").replace("\\","/")}

    config = Settings().config["macro_config"]

    macroFunctions = []

    def __init__(self) -> None:
        super().__init__()
        self.view = QMacroConfigWidget()

        self.init_ui_data()
        self.init_ui_eventbind()
        self.init_ui_with_config()

        self.connect_ui_save_event_bind()
        self.generate_config()

    def generate_config(self):
        # if not os.path.exists(self.config_files["config_file"]):
            # self.save_config()
        self.save_config()


    def init_ui_data(self) -> None:

        for macroMode in MacroMode:
            self.view.driversoft.addItem(macroMode.value, userData=macroMode)

        for aimMode in AimMode:
            self.view.modes.addItem(aimMode.value, userData=aimMode)

        for index, modifier in enumerate(["lctrl","lshift","lalt","ralt","rctrl","rshit"]):
            self.view.add_modifier_key(modifier, index)

        for button in range(1,12):
            self.view.selectBtn.addItem(f"G{button}",userData=button)
        self.view.selectBtn.setCurrentIndex(-1)
        
        self.load_macro_functions()
        self.view.selectFunc.setCurrentIndex(-1)

        self.tablemodel = KeyBindingTableModel(self.view, [], ["修饰键", "鼠标按键", "功能"])
        self.view.table.setModel(self.tablemodel)
        
    def init_ui_eventbind(self) -> None:
        self.view.driversoft.currentIndexChanged.connect(self.driver_changed)
        self.view.modes.currentIndexChanged.connect(lambda:self.mode_changed()) # bug 无法直接绑定
        self.view.driver_script_download_btn.clicked.connect(self.download_driverscript)
        
        for modifier_checkbox in self.view.modifier_checkboxs:
            modifier_checkbox.stateChanged.connect(self.update_edit_keybinding)
        self.view.selectBtn.currentIndexChanged.connect(self.update_edit_keybinding)
        self.view.selectFunc.currentIndexChanged.connect(self.update_edit_keybinding)

        self.view.minusBtn.clicked.connect(self.table_del_row)
        self.view.addBtn.clicked.connect(self.table_add_row)
        self.view.editBtn.clicked.connect(self.macro_edit_dialog)
        self.view.table.selectionModel().selectionChanged.connect(self.table_select_row)

    def init_ui_with_config(self):
        self.view.driversoft.setCurrentIndex( -1 )
        self.view.driversoft.setCurrentIndex( self.view.driversoft.findData(MacroMode(self.config["driver"])) )
        self.view.modes.setCurrentIndex( self.view.modes.findData(AimMode(self.config["adsmode"])) )
        keyBindings = []
        for key in self.config["keybinds"]:
            modifiers = key.split("+")[0].split(",")
            if len(modifiers) == 1 and modifiers[0] == "":
                modifiers = []
            mouseBtn = key.split("+")[-1]
            try:
                scriptFunc = self.macroFunctions[self.config["keybinds"][key]] 
            except:
                continue

            keyBindings.append(KeyBinding(mouseBtn=mouseBtn,func=scriptFunc,modifiers=modifiers))
        self.tablemodel.set_datas(keyBindings)
        self.tablemodel.sort_data()
        
    def connect_ui_save_event_bind(self):
        self.view.driversoft.currentIndexChanged.connect(self.save_config)
        self.view.modes.currentIndexChanged.connect(self.save_config)
        
        for modifier_checkbox in self.view.modifier_checkboxs:
            modifier_checkbox.stateChanged.connect(self.save_config)
        self.view.selectBtn.currentIndexChanged.connect(self.save_config)
        self.view.selectFunc.currentIndexChanged.connect(self.save_config)
        self.view.minusBtn.clicked.connect(self.save_config)

    def save_config(self):

        ## table to config

        keyBinding_data = self.tablemodel.data.copy()
        keyBinding_data.append(KeyBinding(1,self.macroFunctions["leftbutton"]))
        rightkey = 2
        if self.view.driversoft.currentData() == MacroMode.GHUB2:
            rightkey = 3
        keyBinding_data.append(KeyBinding(rightkey,self.macroFunctions["rightbutton"]))

        ## render config.lua
        result = ""
        for keyBinding in keyBinding_data:
            functionname =keyBinding.func.name
            result += f"function {functionname}(vars)\n"
            result += keyBinding.func.openContent
            result += "\nend\n\n"
            if keyBinding.func.closeContent != None:
                result += f"function {functionname}_release(vars)\n"
                result += keyBinding.func.closeContent
                result += "\nend\n\n"

        for key in ["dorecoil","ads"]:
            result += f"function {key}(vars)\n"
            result += self.macroFunctions[key].openContent
            result += "\nend\n\n"

        # bindkeys
        result += "function bindkeys(config,vars)\n"
        keys_without_modifiers = []
        keys_with_modifiers = []
        for keyBinding in keyBinding_data:
            result += f"config[\"{keyBinding.get_key()}\"]={{\n"
            result += f"    button={keyBinding.mouseBtn},\n"
            result += "    modifier={{{}}},\n".format(
                "\"" + "\",\"".join(keyBinding.modifiers)+"\"" if len(keyBinding.modifiers)>0 else ""
                )
            result += f"    funcPress=\"{keyBinding.func.name}\",\n"
            if keyBinding.func.closeContent != None:
                result += f"    funcRelease=\"{keyBinding.func.name}_release\",\n"
            result += "}\n"
            key = keyBinding.get_key()
            keys_without_modifiers.append(key) if key.startswith("+") else keys_with_modifiers.append(key)

        keys_with_modifiers.sort(key=lambda x:len(x.split(",")),reverse=True)
        keys_without_modifiers.extend(keys_with_modifiers)
        result += "config[\"keys\"]={{ {} }}\n".format("\"" + "\",\"".join(keys_without_modifiers) + "\"")
        

        for key in self.config:
            if key in ["keybinds"]:
                continue

            value = self.config[key]

            if isinstance(value,bool):
                value = "true"  if value==True else "false"
                result += f"vars[\"{key}\"]={value}\n"
                continue

            if isinstance(value,int):
                result += f"vars[\"{key}\"]={int(value)}\n"
                continue

            result += f"vars[\"{key}\"]=\"{str(value)}\"\n"
            continue

        for key in self.config_files:
            result += f"vars[\"{key}\"]=\"{self.config_files[key]}\"\n"

        result +=  self.macroFunctions["bindkeys"].openContent
        result += "\nend\n\n"

        with open(self.config_files["config_file"],"w",encoding="UTF-8") as f:
            f.write(result)

        self.config["keybinds"] = {}
        for keybind in self.tablemodel.data:
            self.config["keybinds"][keybind.get_key()] = keybind.func.name

        Settings().save_config_to_json()

    def load_functions(self, script_file_path: str) -> str:
        with open(script_file_path, "r") as f:
            scripts = json.load(f)
        return scripts

    def parse_functions_to_model(self, scripts: str) -> list:
        result = {}
        for script in scripts:
            name = script
            openContent = scripts[script][0]
            closeContent = scripts[script][1]
            description = scripts[script][2]
            custome = scripts[script][3]
            macroFunction = MacroFunction(name=name, openContent=openContent,
                                          closeContent=closeContent, description=description, custome=custome)
            result[name]=macroFunction
        return result
    
    def download_driverscript(self):
        save_path = self.view.save_file_dialog()
        if not save_path:
            return

        mainscript = self.macroFunctions["script"]
        result = mainscript.openContent.format(
            "C:/Users/Dip/AppData/Local/jhwd"+"/config.lua")
        with open(save_path, "w") as f:
            f.write(result)

    def mode_changed(self):
        self.config["adsmode"] = self.view.modes.currentData().value

    def keybinding_edit_ui_block_event(self,block:bool):
        for modifier_checkbox in self.view.modifier_checkboxs:
            modifier_checkbox.blockSignals(block)
        self.view.selectFunc.blockSignals(block)
        self.view.selectBtn.blockSignals(block)

    def table_select_row(self):
        row = self.view.table.currentIndex().row()

        keybinding = self.tablemodel.get_data(row)

        self.keybinding_edit_ui_block_event(True)

        if keybinding != None:
            for modifier_checkbox in self.view.modifier_checkboxs:
                if modifier_checkbox.text() in keybinding.modifiers:
                    modifier_checkbox.setChecked(True)
                else:
                    modifier_checkbox.setChecked(False)
            self.view.selectBtn.setCurrentIndex(self.view.selectBtn.findData(keybinding.mouseBtn))
            self.view.selectFunc.setCurrentIndex(self.view.selectFunc.findData(keybinding.func))
        else:
            for modifier_checkbox in self.view.modifier_checkboxs:
                    modifier_checkbox.setChecked(False)
            self.view.selectBtn.setCurrentIndex(-1)
            self.view.selectFunc.setCurrentIndex(-1)

        self.keybinding_edit_ui_block_event(False)
        
    def update_edit_keybinding(self):
        modifiers = list(filter(lambda checkbox:checkbox.isChecked(),self.view.modifier_checkboxs))
        modifiers = [ m.text() for m in modifiers]
        keyBinding = KeyBinding(mouseBtn=self.view.selectBtn.currentData(),
                                func=self.view.selectFunc.currentData(),
                                modifiers=modifiers
                                )
        if keyBinding.is_valid():
            row = self.view.table.currentIndex().row()
            self.tablemodel.set_data(row, keyBinding)

    
    def table_add_row(self):
        self.tablemodel.append_data(None)

    def table_del_row(self):
        row = self.view.table.currentIndex().row()
        self.tablemodel.remove_row(row)
    
    def driver_changed(self):
        macro = self.view.driversoft.currentData()
        if not macro:
            return
        self.config["driver"] = macro.value
        if macro == MacroMode.LGS:
            self.macroFunctions = self.parse_functions_to_model(self.load_functions(Settings().resource_dir+"lgsscripts.json"))
        if macro == MacroMode.GHUB:
            self.macroFunctions = self.parse_functions_to_model(self.load_functions(Settings().resource_dir+"ghubscripts.json"))
        if macro == MacroMode.GHUB2:
            self.macroFunctions = self.parse_functions_to_model(self.load_functions(Settings().resource_dir+"ghub2scripts.json"))
        self.load_macro_functions()

    def load_macro_functions(self):
        self.keybinding_edit_ui_block_event(True)
        self.view.selectFunc.clear()
        for func in self.macroFunctions:
            func = self.macroFunctions[func]
            if "tablemodel" in dir(self):
                for keybinding in self.tablemodel.data:
                    if keybinding.func.name == func.name:
                        keybinding.func = func
                        break
            if func.custome:
                self.view.selectFunc.addItem(func.description,userData=func) if func.description else self.view.selectFunc.addItem(func.name,userData=func)

        if "tablemodel" in dir(self):
            row = self.view.table.currentIndex().row()
            if row != -1:
                keybinding = self.tablemodel.get_data(row)
                if keybinding:
                    self.view.selectFunc.setCurrentIndex(self.view.selectFunc.findData(keybinding.func))

        self.keybinding_edit_ui_block_event(False)
        
    def save_macro_script(self,func:MacroFunction,openContent: str,closeContent:str, dialog):

        func.openContent = openContent

        func.closeContent = closeContent

        result = {}
        for macro in self.macroFunctions:

            macro = self.macroFunctions[macro]

            key = macro.name

            result[key] = [
                macro.openContent,
                macro.closeContent,
                macro.description,
                macro.custome
            ]

        if self.view.driversoft.currentData() == MacroMode.LGS:
            save_file = Settings().resource_dir+"lgsscripts.json"
        elif self.view.driversoft.currentData() == MacroMode.GHUB: 
            save_file = Settings().resource_dir+"ghubscripts.json"
        elif self.view.driversoft.currentData() == MacroMode.GHUB2: 
            save_file = Settings().resource_dir+"ghub2scripts.json"

        with open(save_file,"w") as file:
            json.dump(result, file, indent=4)
        
        dialog.close()
        self.save_config()


    def macro_edit_dialog(self):
        dialog = MacroEditDialog(self.macroFunctions)
        dialog.save.connect(self.save_macro_script)
        dialog.exec()