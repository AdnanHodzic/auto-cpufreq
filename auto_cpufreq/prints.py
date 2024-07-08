from os import get_terminal_size

COLOR = False
try: terminal_width = min(get_terminal_size(0)[0], 50)
except: terminal_width = 50

def colored(*values:str, color) -> str:
    return f'\x1b[38;5;{color}m{" ".join(values)}\x1b[0m' if COLOR and color else ' '.join(values)

def print_separator(color=None) -> None: print('\n'+colored('─'*terminal_width, color=color))

def print_header(*values:str, color=None) -> str:
    head = ' '.join(values)
    sep = '─'*max(((terminal_width - len(head)) // 2 - 1), 2)
    str = colored(f'{sep} {head} {sep}', color=color)
    print('\n'+str+'\n')
    return str

def print_colon(previous_value:str, *next_values:object, color=None) -> None: print(colored(previous_value, color=color)+':', *next_values)

def print_block(block_title:str, *lines:object, color=None) -> None:
    print_header(block_title, color=color)
    for line in lines: print(line)
    print_separator(color)

def print_error(*values:object) -> None: print_colon('Error', *values, color=9)

def print_info(*values:object) -> None: print_colon('Info', *values, color=12)
def print_info_block(info_title:str, *lines:object) -> None: print_block(info_title+' infos', *lines, color=12)

def print_suggestion(*values:object) -> None: print_colon('Suggestion', *values, color=5)

def print_warning(*values:object) -> None: print_colon('Warning', *values, color=11)
def print_warning_block(*lines:object) -> None: print_block('Warning', *lines, color=11)