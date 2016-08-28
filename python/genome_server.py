#!/usr/bin/env python
# genome_server.py

"""
Main entry point for the Python portion of the project. Loads a chromosome file in the .fa format,
and offers an OSC endpoint that can be used to read through the chromosome, and to consume MIDI events
generated by interpreting the chromosome code.
"""

import sys
import time, threading
import OSC
from chromosome_reader import *
from conductor import *

listening_port = 3337
max_sending_port = 3338
remote_sending_port = 3339
filename = sys.argv[1]

## State setup
cr = ChromosomeReader(filename)
cn = Conductor()

## OSC Handlers --- Max
def density_handler(addr, tags, stuff, source):
	global cn
	channel = stuff[0]
	density = stuff[1]
	cn.setDensity(channel, density)

def get_amino_acid_handler(addr, tags, stuff, source):
	global out_c_max
	global cn
	msg = OSC.OSCMessage()
	msg.setAddress("/aminoAcidCounts")
	for cnt in cn.getAminoAcidCounts():
		msg.append(cnt)
	out_c_max.send(msg)

def ping_handler(addr, tags, stuff, source):
	print addr
	print tags
	print stuff
	print source
	send_echo_event()

def reset_handler(addr, tags, stuff, source):
	"""
	Handles messages with the /reset address. Moves the curson back to the beginning of the current
	chromosome file, and clears all of the current sequencers
	"""
	global filename
	global cr
	global cn
	print "Resetting"
	print source
	cr.loadChromosomeFile(filename)
	cn.reset()

def read_handler(addr, tags, stuff, source):
	"""
	Handles messages with the /read address. Advances the cursor through the genome by a single amino
	acid. Sends a message with the /ready address when the amino acid has been read
	"""
	global cr
	global cn

	toRead = 1
	if len(stuff) > 0:
		toRead = int(stuff[0])

	for _ in range(toRead):
		if cr.hasNext():
			cn.addAmino(cr.nextAmino())
		else:
			break
	send_read_complete_event()

def step_handler(addr, tags, stuff, source):
	"""
	Handles messages with the /step address. The message should have a single argument, an integer
	that is the current beat. Will send a message to /midi with all of the midi messages associated with
	that beat.
	"""
	midiEvents = cn.processStep(stuff[0])
	send_midi_events(midiEvents)

def transport_handler(addr, tags, stuff, source):
	send_transport_status(stuff)

## OSC Senders --- Max
def send_midi_events(events):
	global out_c_max
	msg = OSC.OSCMessage()
	msg.setAddress("/midi")
	for event in events:
		for i in event:
			msg.append(i)
	out_c_max.send(msg)

def send_echo_event():
	global out_c_max
	msg = OSC.OSCMessage()
	msg.setAddress("/echo")
	msg.append(time.time())
	out_c_max.send(msg)

def send_read_complete_event():
	global out_c_max
	global cr
	msg = OSC.OSCMessage()
	msg.setAddress("/ready")
	msg.append(cr.getBasePairsRead())
	msg.append(cr.getAminoAcidsRead())
	out_c_max.send(msg)

def send_transport_event(typp):
	global out_c_max
	msg = OSC.OSCMessage()
	msg.setAddress("/transport")
	msg.append(typp)
	out_c_max.send(msg)

def send_transport_status(stuff):
	global out_c_remote
	msg = OSC.OSCMessage()
	msg.setAddress("/rprint")
	msg.append("transport: ")
	for s in stuff:
		msg.append(s)
	out_c_remote.send(msg)

## OSC Handlers --- Remote
def remote_jump_handler(addr, tags, stuff, source):
	global cr
	global filename
	cr.loadChromosomeFile(filename)
	cr.seekPosition(stuff[0])
	msg = OSC.OSCMessage()
	msg.setAddress("/rprint")
	msg.append("Jump complete")
	out_c_remote.send(msg)

def remote_open_handler(addr, tags, stuff, source):
	global cr
	global filename
	filename = "../data/chromosomes/chr{}.fa".format(stuff[0])
	cr.loadChromosomeFile(filename)

def remote_ping_handler(addr, tags, stuff, source):
	global out_c_remote
	msg = OSC.OSCMessage()
	msg.setAddress("/recho")
	msg.append(time.time())
	out_c_remote.send(msg)

def remote_reset_handler(addr, tags, stuff, source):
	reset_handler(addr, tags, stuff, source)

def remote_transport_handler(addr, tags, stuff, source):
	if stuff and stuff[0] in ["start", "stop", "continue", "currenttime"]:
		send_transport_event(stuff[0])

def remote_status_handler(addr, tags, stuff, source):
	global out_c_remote
	global cr
	print "status handler"
	msg = OSC.OSCMessage()
	msg.setAddress("/rprint")
	msg.append("status---")
	msg.append("filename:")
	msg.append(cr.filename)
	msg.append("aminos_read:")
	msg.append(cr.aminoAcidsRead)
	msg.append("estimated_aminos:")
	msg.append(cr.estimatedTotalAminos)
	out_c_remote.send(msg)

## Receiving messages
in_c = OSC.OSCServer(('127.0.0.1', listening_port))

##		Messages from Max
in_c.addMsgHandler('/density', density_handler)
in_c.addMsgHandler('/getAminoAcidCounts', get_amino_acid_handler)
in_c.addMsgHandler('/ping', ping_handler)
in_c.addMsgHandler('/read', read_handler)
in_c.addMsgHandler('/reset', reset_handler)
in_c.addMsgHandler('/step', step_handler)
in_c.addMsgHandler('/transport', transport_handler)

##		Messages from Remote
in_c.addMsgHandler('/rjump', remote_jump_handler)
in_c.addMsgHandler('/ropen', remote_open_handler)
in_c.addMsgHandler('/rping', remote_ping_handler)
in_c.addMsgHandler('/rreset', remote_reset_handler)
in_c.addMsgHandler('/rtransport', remote_transport_handler)
in_c.addMsgHandler('/rstatus', remote_status_handler)

## Sending messages
out_c_max = OSC.OSCClient()
out_c_max.connect(('127.0.0.1', max_sending_port))
out_c_remote = OSC.OSCClient()
out_c_remote.connect(('127.0.0.1', remote_sending_port))

############################## Start OSCServer
print "\nStarting OSCServer, listening on port {}, sending to port {}. Use ctrl-C to quit.".format(listening_port, max_sending_port)
st = threading.Thread( target = in_c.serve_forever )
st.start()

try :
    while 1 :
        time.sleep(5)

except KeyboardInterrupt :
    print "\nClosing OSCServer."
    in_c.close()
    print "Waiting for Server-thread to finish"
    st.join() ##!!!
    print "Done"