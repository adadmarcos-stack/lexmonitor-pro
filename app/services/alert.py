import smtplib
from email.mime.text import MIMEText


def enviar_alerta_email(assunto, mensagem):
    try:
        remetente = "adadjammal@gmail.com"
        senha = "cwjv wjfk ytdq ldlv"

        destinatario = "adadjammal@gmail.com"

        msg = MIMEText(mensagem)
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = destinatario

        with smtplib.SMTP("smtp.gmail.com", 587) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha)
            servidor.send_message(msg)

        return True

    except Exception as e:
        print("Erro ao enviar e-mail:", e)
        return False