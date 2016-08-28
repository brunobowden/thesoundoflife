from amino_acid import *
from polypeptide import *
from sequence import *
# from graphics import *

smallSequenceCount = 4
smallSequenceSize = 16
smallSequenceBPSize = 90
smallSequenceOptions = {
}
mediumSequenceCount = 2
mediumSequenceSize = 32
mediumSequencesBPSize = 120
mediumSequenceOptions = {
}
largeSequenceCount = 1
largeSequenceSize = 16
largeSequenceBPSize = 150
largeSequenceOptions = {
}

maxAminoCount = 200

class SequenceGroup:
	def __init__(self, seqCount, size, channelOffset, options={}):
		self.sequences = [None for _ in range(seqCount)]
		self.seqIndex = 0
		self.pendingSequences = []
		self.sequenceIndexesToRemove = []
		self.channelOffset = channelOffset
		self.size = size
		self.fixedDensity = options.get("fixedDensity", 1.0)
		self.maxAge = options.get("maxAge", -1)

	def getSize(self):
		return self.size

	def appendPendingSequence(self, seq):
		self.pendingSequences.append(seq)

	def isDownbeat(self, step):
		return step % self.size == 0

	def flushPendingSequences(self):
		for idx in self.sequenceIndexesToRemove:
			self.sequences[idx] = None
		self.sequenceIndexesToRemove = []
		for s in self.pendingSequences:
			s.setDensity(self.fixedDensity)
			self.sequences[self.seqIndex] = s
			self.seqIndex = (self.seqIndex + 1)  % len(self.sequences)
		self.pendingSequences = []

	def getSequences(self):
		return self.sequences

	def getChannelOffset(self):
		return self.channelOffset

	def removeSequenceAtIndex(self, idx):
		if idx not in self.sequenceIndexesToRemove:
			print "Removing sequence at index {}".format(idx)
			self.sequenceIndexesToRemove.append(idx)

class Conductor:
	def __init__(self):
		self.polypeptides = []
		self.isSynthesizingPolypeptide = False
		self.inProgressPolypeptide = None
		self.aminoAcidCounts = [0 for _ in range(20)]

		self.totalSequences = 0
		self.smallSequences = SequenceGroup(smallSequenceCount, smallSequenceSize, 1 + self.totalSequences, smallSequenceOptions)
		self.totalSequences += smallSequenceCount
		self.mediumSequences = SequenceGroup(mediumSequenceCount, mediumSequenceSize, 1 + self.totalSequences, mediumSequenceOptions)
		self.totalSequences += mediumSequenceCount
		self.largeSequences = SequenceGroup(largeSequenceCount, largeSequenceSize, 1 + self.totalSequences, largeSequenceOptions)
		self.totalSequences += largeSequenceCount

		self.sequenceGroups = [self.smallSequences, self.mediumSequences, self.largeSequences]
		# self.win = GraphWin()

	def addAmino(self, aa):
		if self.isSynthesizingPolypeptide:
			if (aminoIsStopCodon(aa)):
				# self.polypeptides.append(self.inProgressPolypeptide)

				if (self.inProgressPolypeptide.size() > largeSequenceBPSize):
					s = Sequence(self.inProgressPolypeptide, largeSequenceSize, {"stepRate": 32})
					self.largeSequences.appendPendingSequence(s)
					print "New large sequence"
				elif (self.inProgressPolypeptide.size() > mediumSequencesBPSize):
					s = Sequence(self.inProgressPolypeptide, mediumSequenceSize, {"stepRate": 2})
					self.mediumSequences.appendPendingSequence(s)
					print "New medium sequence"
				elif (self.inProgressPolypeptide.size() > smallSequenceBPSize):
					s = Sequence(self.inProgressPolypeptide, smallSequenceSize)
					self.smallSequences.appendPendingSequence(s)
					print "New small sequence"
				
				## TODO Handle incidental polypeptides like this

				# 	self.inProgressPolypeptide.graphicsDraw(self.win, Point(50, 50))
				self.isSynthesizingPolypeptide = False
				self.inProgressPolypeptide = None
			else:
				self.inProgressPolypeptide.addAmino(aa)
		elif (aminoIsStartCodon(aa)):
			self.isSynthesizingPolypeptide = True
			self.inProgressPolypeptide = Polypeptide()

		## Count the amino for LFO's
		if not aminoIsStopCodon(aa):
			aa_idx = aminoToIndex(aa)
			self.aminoAcidCounts[aa_idx] = (self.aminoAcidCounts[aa_idx] + 1)

	def processStep(self, step):
		## If the step is a downbeat, and you've got sequences to swap, then do it here
		for sg in self.sequenceGroups:
			if (sg.isDownbeat(step)):
				sg.flushPendingSequences()
			for sidx, seq in enumerate(sg.getSequences()):
				if seq is not None:
					seq.age += 1
					if sg.maxAge > -1:
						if seq.age > sg.maxAge:
							sg.removeSequenceAtIndex(sidx)

		# Now generate MIDI for all the events
		midiEvents = []
		for sg in self.sequenceGroups:
			for seqIdx, seq in enumerate(sg.getSequences()):
				if seq is not None:
					seqMidiEvents = seq.midiEventsForStep(step, sg.getChannelOffset() + seqIdx)
					midiEvents = midiEvents + seqMidiEvents
		return midiEvents

	def reset(self):
		self.polypeptides = []
		self.isSynthesizingPolypeptide = False
		self.inProgressPolypeptide = None
		self.aminoAcidCounts = [0 for _ in range(20)]
		
		self.totalSequences = 0
		self.smallSequences = SequenceGroup(smallSequenceCount, smallSequenceSize, 1 + self.totalSequences)
		self.totalSequences += smallSequenceCount
		self.mediumSequences = SequenceGroup(mediumSequenceCount, mediumSequenceSize, 1 + self.totalSequences)
		self.totalSequences += mediumSequenceCount
		self.largeSequences = SequenceGroup(largeSequenceCount, largeSequenceSize, 1 + self.totalSequences)
		self.totalSequences += largeSequenceCount

		self.sequenceGroups = [self.smallSequences, self.mediumSequences, self.largeSequences]

	def getAminoAcidCounts(self):
		return self.aminoAcidCounts

	def setDensity(self, channel, density):
		for sg in self.sequenceGroups:
			if channel >= sg.getChannelOffset() and channel < sg.getChannelOffset() + len(sg.getSequences()):
				seq = sg.getSequences()[channel - sg.getChannelOffset()]
				if seq is not None:
					seq.setDensity(density)