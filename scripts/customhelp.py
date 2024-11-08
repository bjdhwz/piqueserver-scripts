"""
Help in different languages

.. codeauthor:: Liza
"""

from piqueserver.commands import command


@command()
def eshelp(connection):
    connection.send_lines([
        "Bienvenido a BUILD EMPIRE",
        "Utilice /free para encontrar un sector no reclamado y teleportarse aqui con /gt",
        "Registrarse con un comando /reg para proteger su sector con un comando /claim",
        "Reglas: 1) no construyas arte/cuadros/banderas, construye edificios",
        "2) no arruines el juego por otros"
        ])

@command()
def ruhelp(connection):
    connection.send_lines([
        "Dobro pozhalovat' na BUILD EMPIRE",
        "Ispol'zuy /free chtoby nayti nezanyatyy sektor i tp'shsya tuda komandoy /gt",
        "Registriruysya komandoy /reg chtoby zaschitit' svoy sektor komandoy /claim",
        "Pravila: 1) ne nado delat' arty/kartinki/flagi, stroy zdaniya",
        "2) ne port' igru drugim"
        ])

@command()
def slavhelp(connection): # Interslavic language
    connection.send_lines([
        "Prosim do BUILD EMPIRE",
        "Poljzuj /free da by najdti svobodny sektor i tp tudy komandoju /gt",
        "Registruj se komandoju /reg da by zashchititi svoj sektor komandoju /claim",
        "Pravila: 1) ne treba delati arty/flagi, delaj budynky",
        "2) ne ruinuj igru drugym"
        ])


def apply_script(protocol, connection, config):
    return protocol, connection
