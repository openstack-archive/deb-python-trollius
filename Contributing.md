There are two items here: how to submit your patch for review (known as "pull requests" in the git world), and the red tape necessary before your first patch is accepted.

# Submitting patches #

The preferred way to submit patches for review is to use Rietveld (https://codereview.appspot.com/). You need a Google Account in order to use this; it will send email responses to the email address associated with your account (not necessarily a GMail address).

You also need a Mercurial checkout of the Tulip project -- see the Source tab above. (Yes, you may have to install Mercurial. It's shaving yaks all the way down. :-)

To get started with your first code review, download the upload.py script from https://codereview.appspot.com/static/upload.py and install it in your personal 'bin' directory (or somewhere else along your shell's $PATH).

Instructions on how to use upload.py are at http://code.google.com/p/rietveld/wiki/UploadPyUsage. In my own workflow, I don't usually commit patches to my local repo while they're being reviewed; the script is optimized for this case, and I basically just have to type "upload.py" in my working directory.

It's important to get the tool to send email to a reviewer. The easiest way to do this is to use the --reviewers and --send\_mail options on the upload.py script. You can also go to the URL printed by the script and click on the "Publish+Mail Comments" link; then enter the reviewer's email address and click "Publish all my drafts" (never mind that you probably don't have any drafts comments).

Who to send reviews to? You can use the python-tulip mailing list or send them to Guido. (The email addresses are not in this wiki to deter spammers.)

# Red Tape #

Python and Tulip are open source, and that brings along a small amount of red tape. Before we can accept contributions you must agree to the Python Software Foundation's Contributor Agreement: http://www.python.org/psf/contrib/contrib-form/. Fortunately signing it once covers all your current and future contributions to Python and Tulip (and any other software covered by the PSF license). Do beware that if your contribution was created on your employer's behalf the rules are different, and your manager has to sign.