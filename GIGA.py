import requests

url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

payload={
  'scope': 'GIGACHAT_API_PERS'
}
headers = {
  'Content-Type': 'application/x-www-form-urlencoded',
  'Accept': 'application/json',
  'RqUID': 'db531052-566a-4d4e-ab6f-7d2265421882',
  'Authorization': 'Basic MDE5OWYzOTQtZjY0YS03MGM5LWJlNDctN2U4NzA4NGZiYTY5OjgzN2ZiMjhkLWQwMTAtNGE1YS04MGYyLWRiMjgxN2FiZTA2Zg=='
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)