import bcrypt

password = input("Enter password: ")

hashed = bcrypt.hashpw(
    password.encode("utf-8"),
    bcrypt.gensalt()
)

print(hashed.decode("utf-8"))