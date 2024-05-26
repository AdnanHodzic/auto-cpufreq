from os import get_terminal_size

COLOR = False
try: terminal_width = get_terminal_size(0)[0]
except: terminal_width = 50

def colored(*values:object, color:int|None) -> str:
    return f'\x1b[38;5;{color}m{" ".join(values)}\x1b[0m' if COLOR and color is not None else ' '.join(values)

def print_newlines(*values:object, color:int|None=None) -> None: print('\n'+colored(*values, color=color)+'\n')

def print_separator(color:int|None=None) -> None: print('\n'+colored('─'*terminal_width, color=color))

def print_header(*values:object, color:int|None=None) -> None:
    head = ' '.join(values)
    sep = '─'*((terminal_width - len(head)) // 2 - 1)
    print_newlines(f'{sep} {head} {sep}', color=color)

def print_colon(previous_value:object, *next_values:object, color:int|None=None) -> None: print(colored(previous_value, color=color)+':', *next_values)

def print_block(block_title:object, *lines:object, color:int|None=None) -> None:
    print_header(block_title, color=color)
    for line in lines: print(line)
    print_separator(color)

def print_error(*values:object) -> None: print_colon('Error', *values, color=9)

def print_info(*values:object) -> None: print_colon('Info', *values, color=12)
def print_info_block(info_title:object, *lines:object) -> None: print_block(info_title+' infos', *lines, color=12)

def print_suggestion(*values:object) -> None: print_colon('Suggestion', *values, color=5)

def print_warning(*values:object) -> None: print_colon('Warning', *values, color=11)
def print_warning_block(*lines:object) -> None: print_block('Warning', *lines, color=11)