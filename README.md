# nametag-coding-challenge

Write a client-side program that will update itself when a new version is released.

#### 2 parts
 - server
 - client program

Server will update via standard CICD and have endpoints like 
```
GET /latest_version
GET /latest_binary
POST /result
```

#### Client update process:
 - client polls server for latest version
 - on new version, fetch new binary
 - install and run tests (client CICD)
 - swap to new version if tests are succesful 
 - send success/failure result to server (acts as telemetry interface)

what could go wrong......
 - client disk space at capacity
 - network/download issues messing up the new binary

how many logs do we want about a client with a full disk? should there be a limit to retries on a particular version so we dont get spammed? perhaps a long horizon exponential backoff.

=== 

hosting a server seems unnecessary. why not just have the client read from a dynamodb table. somthing like
```python
{
    'version': ...,
    'sha': ...,
    'url': s3 link to binary
} 
```

but what about auth. it would need to be a presigned url and the dynamodb table would need to be locked down too...

ok so:

    client -> auth server 

       -> api gateway -> lambda for presigned url 

and then same process for logs 

what do I do if the update is successful but for whatever reason needs to be rolled back, but only on certain clients? if the lambda could ID the client / OS arch, it could first check a lookup table to see if any custom version requirements have been set 