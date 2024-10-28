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
        ], 'rules')

@command()
def ruhelp(connection):
    connection.send_lines([
        "Dobro pozhalovat' na BUILD EMPIRE",
        "Ispol'zuy /free chtoby nayti nezanyatyy sektor i tp'shsya tuda komandoy /gt",
        "Registriruysya komandoy /reg chtoby zaschitit' svoy sektor komandoy /claim",
        "Pravila: 1) ne nado delat' arty/kartinki/flagi, stroy zdaniya",
        "2) ne port' igru drugim"
        ], 'rules')


def apply_script(protocol, connection, config):
    return protocol, connection
