from django.apps import AppConfig


class BattleConfig(AppConfig):
    name = "cbattle"
    dpy_package = "cbattle.extension" 

    def ready(self): 
        print("cbattle ready")
