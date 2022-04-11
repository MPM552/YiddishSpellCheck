#!/usr/bin/perl  -T

=head1 SYNOPSYS

checkSpellUTF.cgi

Fixes spelling and shows problems.

Author: Raphael Finkel 10/2010  8/2020 GPL

=cut

use strict;
use utf8;
use CGI qw/:standard -debug -utf8/;
$CGI::POST_MAX = 1024 * 1024 * 10;  # max 10MB posts
use Encode;
$ENV{'PATH'} = '/bin:/usr/bin:/usr/local/bin:/usr/local/gnu/bin'; # for security

# constants
# my $version = "1.2";
	# added ability to show only misspelled words.
	# added ability to double-click bad words to place in a list at end.
my $version = "1.3";
	# can convert Microsoft format files (such as .docx)
my $spellFile = 'wordlist.utf8.txt';
my $nonsense = 'X'; # never appears in a normal word
my @corrections = (
	'ײ ײַ',
	'ת תּ',
	'כ כּ',
	'ב בֿ',
	'פ פֿ',
	'פ פּ',
	'יע יִע',
	'יו יִו',
	'עי עיִ',
	'א(?=\P{M}|$) אַ',
	'א(?=\P{M}|$) אָ',
	'ש(?=\P{M}|$) שׂ',
	'אַי אַיִ',
	'ײ עי',
	'נז נדז',
	'יג\b יק', # maybe too invasive, but Khsidish Yiddish has this problem
	'װאו װוּ',  # Morgn-zhurnal -> YIVO
	'ײאי ײיִ',
	'ואװ וּװ',
	'ואו ווּ',
	'ױאי ױיִ',
	'ואי ויִ',
	'װאױ װױ',
	'אַאי אַיִ',
);

# global variables
my (
	$text, # the document to peruse
	%okWords, # each ok word just maps to 1
	%corrected, # cache for attempted corrections, successful or not
	$reduced, # Boolean: if set, we only want to see unexpected words
	$goodWords, # set of words that are to be considered OK.
);

%corrected = ( # common words that we prefer to uncommon ones.
	יאר => 'יאָר',
	אפט => 'אָפֿט',
	שאד => 'שאָד',
	זאל => 'זאָל',
	זאלן => 'זאָלן',
	קאפ => 'קאָפּ',
	נאר => 'נאָר',
	שעפן => 'שעפּן',
	נאמען => 'נאָמען',
	פאלק => 'פֿאָלק',
	הױפט => 'הױפּט',
	װאכן => 'װאָכן',
	פארהאנג => 'פֿאָרהאַנג',
	דערמאנטער => 'דערמאָנטער',
);

my $form = "
	<div dir='ltr'>
	Version $version of the Yiddish spellchecker by Refoyl.
	<form
	action=''
	accept-charset='UTF-8'
	method=\"post\" enctype=\"multipart/form-data\">
		Text in Yiddish Unicode for spelling check:<br/>
		<textarea name=\"Text\" rows=\"5\" cols=\"50\"
		autocorrect='off' autocapitalize='none'
		autocomplete='off' spellcheck='false'
		></textarea>
		<br/>
		or upload from this file (text or docx): 
		<input type=\"file\" name=\"File\" size=\"40\"/> 
		<br/>
		or specify a URL of a document to check (text or docx):
		<input type=\"text\" name=\"URL\" size=\"40\"/> 
		<br/>
		Check this box if you only want to see misspelled words:
		<input type=\"checkbox\" name=\"reduced\" />
		<br/>
		File of words you want to ignore:
		<input type=\"file\" name=\"GoodWords\" size=\"40\"/> 
		<br/>
		<input type=\"submit\" value=\"submit\"
			style=\"background-color:#AAFFAA;\"/>
		<input type=\"reset\" value=\"clear\"
			style=\"background-color:#FFAAAA;\"/>
	</form></div>
	";
my $css = "
	.fixed {background-color:yellow}
	.bad {background-color:#FFB0A0}
	.wasbad {background-color:#AAFFAA}
";
my $legend = "
	<div dir='ltr'>
	Version $version of the Yiddish spellchecker by Refoyl.
	<ul><li>
	This text has been converted to a particular standard:
		<ul><li>Double-vov, vov-yud, double-yud are now single characters.
		</li><li>Precombined characters (like komets-alef) are now a base
		character (like alef) followed by a mark character (like komets).
		</li></ul>
	</li><li>
	Words in <span class='fixed'>this color</span> required simple fixes
	(such as adding pintlekh).
	</li><li>
	Words in <span class='bad'>this color</span> seem misspelled.
	We only show each such word once.  If you double-click this word, it appears
	in a list at the end of the page; you can copy and paste this list into your
	own file.
	</li><li>
	Words in <span class='wasbad'>this color</span> have problems, but they are
	already mentioned earlier with a different color or are
	on the short list of standard corrections.
	</li><ul></div><br/><hr/><br/>";

sub fixit {
	my ($word, $where) = @_;
	return $word if $where >= length($word);
	# print STDERR (" " x $where) . "fixit [$word] at $where\n";
	my $orig = $word;
	my $answer;
	return $word if (defined $okWords{$word});
	for my $correction (@corrections) { # try a correction
		my ($target, $replace) = split(/\s+/, $correction);
		# print STDERR "considering $target => $replace at $where\n";
		pos($word) = $where;
		if ($word =~ s/\G$target/$nonsense/) {
			$word =~ /$nonsense/gc; # must be gc, must not be substitution
			my $position = pos($word);
			$word =~ s/$nonsense/$replace/;
			# print STDERR (" " x $where) . "changed [$orig] to [$word]\n";
			# print STDERR (" " x $where) . "trying $word at $position\n";
			return $word if defined $okWords{$word};
			$answer = fixit($word, $where+1);
				# further fixes, including this one
			return($answer) unless $answer eq $word;
			# print STDERR (" " x $where) . "no joy\n";
			$word = $orig; # so we can try again
		} # try a substitution
	} # each possible correction
	return(fixit($orig, $where+1)); # further fixes, but not this one
} # fixit

sub finalize {
	# $form =~ s/entry/entry1/g;
	print end_html(), "\n";
	close BUCH;
} # finalize

sub untaint {
	my ($string) = @_;
	$string =~ s/[^\w\s־]//g; # only alphabetic characters make sense.
	$string =~ /(.*)/; # remove taint
	$string = $1;
	# print STDERR "string [$string]\n";
	return ($string);
} # untaint

sub standardize { # to combining, not precomposed
	my ($data) = @_;
	$data =~ s/‫//g; # directional marker
	$data =~ s/‬//g; # directional marker
	$data =~ s/וו/װ/g;
	$data =~ s/וי/ױ/g;
	$data =~ s/\bיי(?=\P{M})/ייִ/g;
	$data =~ s/יי/ײ/g;
	$data =~ s/ײַ/ײַ/g;
	$data =~ s/ײִ/ייִ/g;
	$data =~ s/ױִ/ויִ/g;
	$data =~ s/וּי/ויִ/g; # add khirik, remove dagesh
	$data =~ s/וױי(?=\P{M})/װײ/g;
	$data =~ s/­//g; # soft hyphenation mark
	$data =~ s/שׂ/שׂ/g; # combining, not precomposed
	$data =~ s/בּ/בּ/g; # combining, not precomposed
	$data =~ s/כּ/כּ/g; # combining, not precomposed
	$data =~ s/וּ/וּ/g; # combining, not precomposed
	$data =~ s/אָ/אָ/g; # combining, not precomposed
	$data =~ s/אַ/אַ/g; # combining, not precomposed
	$data =~ s/תּ/תּ/g; # combining, not precomposed
	$data =~ s/פֿ/פֿ/g; # combining, not precomposed
	$data =~ s/בֿ/בֿ/g; # combining, not precomposed
	$data =~ s/פּ/פּ/g; # combining, not precomposed
	$data =~ s/אַָ/אָ/g; # remove extraneous pasekh
	$data =~ s/בּ/ב/g; # remove extraneous dagesh
	$data =~ s/⸗/־/g; # DOUBLE OBLIQUE HYPHEN => hyphen
	return($data);
} # standardize

sub checkSpell {
	my $remainder = ''; # first part of a hyphenated word at end of line
	if ($text !~ /\S/) { # empty
		print $form;
		return;
	}
	print $legend;
	print "<span id='text'>\n";
	for my $line (split /\n/, $text) {
		# print STDERR "working on $line";
		print "<p>\n" unless $reduced;
		if ($remainder ne '') {
			$line =~ s/^(\s*)/$1$remainder/;
			$remainder = '';
		}
		if ($line =~ s/(\w+)־$//) {
			$remainder = $1;
		}
		for my $part (split(/([\p{P}\s\d]+)/, $line)) {
			my $better = $part; # unless we get a better idea
			if ($part =~ /\p{L}/ and !defined($okWords{$part})) {
				$better = $corrected{$part};
				if (!defined($better)) {
					# print "fixing [$part] ";
					$better = fixit($part, 0);
					$corrected{$part} = $better;
					if ($better eq $part) { # fixing didn't work
						$better = "<span class='bad'>$better</span>";
					} else { # fixing worked
						$better = "<span class='fixed'>$better</span>";
					}
				} else { # we have already corrected such a word
					if ($reduced) {
						$better = $part;
					} else {
						$better = "<span class='wasbad'>$better</span>";
					}
				} # already corrected
			} # not found
			if ($reduced) {
				print "$better<br/>" unless $better eq $part;
			} else {
				print $better;
			}
		} # each part
		print "<p/>\n" unless $reduced;
	} # one line
	print "</span>\n<hr/>";
	print "<div id='extra'>\x{202a}Words that you have clicked:\x{202c}<br/></div>";
} # checkSpell

sub init {
	binmode STDIN, ":utf8";
	binmode STDOUT, ":utf8";
	binmode STDERR, ":utf8";
	open OKS, $spellFile or die("Cannot read $spellFile\n");
	binmode OKS, ":utf8";
	# print STDERR "reading spelling file\n";
	while (my $line = <OKS>) {
		chomp $line;
		$okWords{$line} = 1;
		# print STDERR "put [$line] in list\n";
	} # one line
	close OKS;
	# print STDERR "done\n";
	printHeader();
	$reduced = defined(param('reduced'));
	if (param('File') ne "") {
		my $InFile = param('File');
		$/ = undef; # read file all at one gulp
		$text = <$InFile>;
		# print STDERR "A File: [$text]\n";
		close $InFile;
		# print "<div>file</div>\n";
		$text = convertFromMicrosoft($text);
		# print "<div>returned</div>\n";
	} elsif (param('URL') ne "") {
		my $URL = param('URL');
		$URL =~ s/['\s"]//g; # remove suspicious characters
		$URL =~ /(.*)/;
		$URL = $1; # remove taint
		open TEXT, "/usr/bin/wget -q -O - '$URL' |";
		binmode TEXT, ":raw";
		$/ = undef;
		$text = <TEXT>;
		close TEXT;
		$text = convertFromMicrosoft($text);
		# print STDERR "text: [$text]\n";
	} else {
		$text = param('Text');
		# $text = param('Text');
	}
	$text =~ s/&#(\d+);/chr($1)/ge; # convert unicode input form.
	$text = standardize($text);
	if (param('GoodWords') ne "") {
		my $InFile = param('GoodWords');
		$/ = undef; # read file all at one gulp
		$goodWords = standardize(decode_utf8(<$InFile>));
		close $InFile;
		# $goodWords =~ s/\p{P}//g; # remove punctuation
		my @goodWords = split /\W+/, $goodWords;
		print "<br>The file of good words has " . (scalar @goodWords) .
			" words.<br>";
		for my $word (@goodWords) {
			next unless $word =~ /\p{L}/;
			$okWords{$word} = 1;
			# print "[$word] is ok<br/>\n";
		}
	} # there is a set of good words
} # init

sub convertFromMicrosoft {
	my ($text) = @_;
	my $tmpDir = "/u/al-d3/csfac/raphael/tmp";
	my $tmpFile = "$tmpDir/checkSpell$$";
	open TEXT, ">$tmpFile";
	binmode TEXT, ":raw";
	print TEXT $text;
	close TEXT;
	my $fileFormat = `/usr/bin/file $tmpFile`;
	# print "<div>format: $fileFormat</div>\n";
	if ($fileFormat =~ /text/) {
		$text = decode('UTF-8', $text, Encode::FB_QUIET);
		# print "<div>after decode: $text</div>\n";
		$text =~ s/^.*<body>//s; # discard initial material
		$text =~ s/<[^>]*>/ /g; # discard all tags
		$text =~ s/\x{200e}//g; # directional mark
		$text =~ s/[a-zA-Z{}]//g; # discard all English
		my @fullText;
		for my $line (split /\n/, $text) {
			push @fullText, $line if $line =~ /\p{Bidi_Class:R}/; # has RTL
		}
		$text = join("\n", @fullText);
		$text =~ s/^.*<body>//s; # discard initial material
	} elsif ($fileFormat =~ /Microsoft/) { # try to convert
		# rename $tmpFile, "$tmpFile.docx";
		#system("/usr/bin/soffice --headless --convert-to txt " .
		#	"--outdir $tmpDir --infilter=text:44,34,76,1 $tmpFile.docx > /dev/null 2>&1");
		system("/usr/bin/docx2txt < $tmpFile > $tmpFile.txt");
		if (open TEXT, "$tmpFile.txt") {
			binmode TEXT, ":utf8";
			$/ = undef;
			# $text = decode('UTF-8', <TEXT>, Encode::FB_QUIET);
			$text = <TEXT>;
			close TEXT;
			# print "<div>after decode: $text</div>\n";
		} else {
			$text = "Conversion from Microsoft™ format failed.";
		}
		unlink ("$tmpFile.txt");
	} else { # unrecognized format; simply say so
		$text = "Unrecognized format: $fileFormat";
	}
	unlink $tmpFile;
	$text =~ s/\x{feff}//g;
	return $text;
} # convertFromMicrosoft

sub printHeader {
	my $analytics = `cat analytics.txt`;
	print header(-type=>'text/html', -charset=>'utf-8', -expires=>'-1d',),
		start_html(-title=>'spellcheck', -dir=>'rtl',
			-onload => "init();",
			-script=>$analytics . "
				var clickedWords = new Array();
				function init() {
					bads = document.getElementsByClassName('bad');
					var index;
					for (index = 0; index < bads.length; index += 1) {
						bads[index].ondblclick = clicked;
					}
				} // init
				function clicked(evt) {
					if(evt.target.tagName == 'SPAN' && evt.target.innerHTML) {
						var newWord = evt.target.innerHTML;
						// alert(newWord);
						// newWord = newWord.replace(/\\W/g, ''); // unnecessary
						if (! clickedWords[newWord]) {
							document.getElementById('extra').innerHTML += '<br\/>' +
								newWord;
							clickedWords[newWord] = 1;
						}
						evt.target.style.backgroundColor = '#AAFFAA';
						window.getSelection().removeAllRanges();
					} 
				} // clicked
				",
			-style=>{-code=>$css});
} # printHeader

init();
checkSpell();
finalize();
