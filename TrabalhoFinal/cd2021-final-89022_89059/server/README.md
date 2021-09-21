# Launching the Server as a container:

```
$ docker pull diogogomes/cd2021:0.1
$ docker run -d --name server diogogomes/cd2021:0.1
```

Want to test a lenghtier password ?

```
$ docker run -d --name server -e PASSWORD_SIZE=2 diogogomes/cd2021
```

# Finding the address of the server:

```
$ docker logs server
