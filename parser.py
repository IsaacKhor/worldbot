import re, traceback
from models import *

NUM_PAT = re.compile(r'^(\d+)')

# Parsing utils
def is_location(tok):
    return tok in ['dwf', 'elm', 'rdi', 'unk']

def is_tents(tok):
    return len(tok) == 3 and all(c in 'mhcsf' for c in tok)

def remove_beginning(item, tok):
    if tok.startswith(item):
        return tok[len(item):].lstrip(' :')
    return tok

def get_beg_number(s):
    num, string = match_beginning(NUM_PAT, s)
    if num:
        num = int(num)
    return num, string

def match_beginning(pat, s):
    m = re.match(pat, s)
    if not m:
        return None, s
    else:
        return m.group(), s[m.span()[1]:].lstrip(' :')

def convert_location(tok):
    if tok == 'rdi':
        return Location.RDI
    if tok == 'elm':
        return Location.ELM
    if tok == 'dwf':
        return Location.DWF
    return Location.UNKNOWN

def parse_update_command(msg):
    """
    Converts a message into a world update command. If the string is not
    an update command return null, otherwise return the world update object.
    """
    msg = msg.strip().lower()

    # Try to match number at beginning of string
    world_num, msg = get_beg_number(msg)
    if not world_num:
        return None

    # Build the world update object
    update = World(world_num, update=True)

    cmd = msg
    time_found = False
    while cmd:
        # Ignore whitespace between tokens
        cmd = cmd.lstrip()

        if cmd.startswith('dead'):
            update.state = WorldState.DEAD
            cmd = remove_beginning('dead', cmd)
            continue

        # Syntax: 'dies :05'
        elif cmd.startswith('dies'):
            cmd = remove_beginning('dies', cmd)
            num, cmd = get_beg_number(cmd)
            if not num:
                continue

            update.time = WbsTime(int(num), 0)
            update.state = WorldState.ALIVE
            continue

        elif cmd.startswith('beaming'):
            update.state = WorldState.BEAMING
            cmd = remove_beginning('beaming', cmd)
            continue

        elif is_tents(cmd[0:3]):
            update.tents = cmd[0:3]
            cmd = cmd[3:]
            continue

        elif is_location(cmd[0:3]):
            update.loc = convert_location(cmd[0:3])
            cmd = cmd[3:]
            continue

        # Syntax: 'beamed :02', space, colon, and time all optional
        elif cmd.startswith('beamed'):
            cmd = remove_beginning('beamed', cmd)
            num, cmd = get_beg_number(cmd)

            update.time = WbsTime.get_abs_minute_or_cur(num).add_mins(10)
            update.state = WorldState.ALIVE
            continue

        # Syntax: 'broken :02', same syntax as beamed
        elif cmd.startswith('broke'):
            cmd = remove_beginning('broken', cmd)
            cmd = remove_beginning('broke', cmd)
            num, cmd = get_beg_number(cmd)

            update.time = WbsTime.get_abs_minute_or_cur(num).add_mins(5)
            update.state = WorldState.ALIVE
            continue

        # Syntax: 'xx:xx gc', the seconds and gc part optional
        # Uses gameclock by default. To override use 'mins' postfix
        # Don't use isnumeric because it accepts wierd unicode codepoints
        # We only want to parse the time once, so if a scout includes
        # numbers in their comments about a world we don't re-parse
        # that as the new time
        elif cmd[0] in '0123456789' and not time_found:
            mins, cmd = get_beg_number(cmd)
            secs, cmd = get_beg_number(cmd)
            secs = secs if secs else 0

            if cmd.startswith('mins'):
                cmd = remove_beginning('mins', cmd)
            else:
                cmd = remove_beginning('gc', cmd)
                ticks = mins*60 + secs
                total_secs = ticks*0.6
                mins, secs = divmod(total_secs, 60)

            update.time = WbsTime.current().add(WbsTime(int(mins), int(secs)))
            update.state = WorldState.ALIVE
            time_found = True
            continue

        # Everything after first unrecognised token are notes
        else:
            update.notes = cmd
            break

    return update


def process_message(worldbot, msgobj):
    text = msgobj.content

    try:
        cmd = text.strip().lower()

        # If we're in ignore mode, just ignore everything
        # except for the command letting us out of it
        if worldbot.ignoremode:
            if cmd == '.ignoremode disable':
                worldbot.ignoremode = False
                return f'Returning to normal mode'
            return

        if cmd.startswith('.ignoremode'):
            worldbot.ignoremode = True
            return f'Going into ignore mode. Use `.ignoremode disable` to get out.'

        elif cmd == 'list':
            worldbot.update_world_states()
            return worldbot.get_current_status()

        elif 'fc' in cmd and '?' in cmd:
            return f'Using FC: "{worldbot.fcnanme}"'

        elif 'good bot' in cmd or 'goodbot' in cmd:
            worldbot._upvotes += 1
            return f'Thank you :D\n{worldbot.get_votes_summary()}'

        elif 'bad bot' in cmd or 'badbot' in cmd:
            # reserved for drizzin XD
            if msgobj.author.id == 493792070956220426:
                return f'Fuck you'

            worldbot._downvotes += 1
            return f':( *cries*\n{worldbot.get_votes_summary()}'

        # Implement original worldbot commands
        elif 'cpkwinsagain' in cmd:
            return msgobj.author.display_name + ' you should STFU!'

        elif cmd[0] in '0123456789':
            update = parse_update_command(text)
            # Falsy return if nothing actually got updated
            return worldbot.update_world(update)

        else:
            for k,v in EASTER_EGGS.items():
                if k in cmd:
                    return v

    except InvalidWorldErr as e:
        return str(e)

    except Exception as e:
        traceback.print_exc()
        return 'Error: ' + str(e) + '\n' + traceback.format_exc()