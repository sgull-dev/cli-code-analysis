## CLI Code Analysis
LLM usage from the terminal, with integrated 'ls' and 'cat' tools.
![Description](img/4.PNG)

### Usage
Place openrouter api key in .env file:
OPENROUTER_API_KEY=[key]

call 
```
python main.py ./dir_to_edit
```

handy to alias in bashrc for use anywhere:
```
alias codetool='python /path/to/main.py .'
```

Swap the model to use from openrouter on the const at the top of main.py.
