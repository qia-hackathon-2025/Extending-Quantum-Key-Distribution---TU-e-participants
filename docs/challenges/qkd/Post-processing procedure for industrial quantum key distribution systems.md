Journal of Physics:
Conference Series
PURPOSE-LED
PUBLISHING™

PAPER • OPEN ACCESS
Post-processing procedure for industrial quantum
key distribution systems

To cite this article: Evgeny Kiktenko et al 2016 J. Phys.: Conf. Ser. 741 012081

View the article online for updates and enhancements.

You may also like
*   Distributed energy storage participates in reactive power optimization strategy research of new distribution system
    Yanping Deng, Ye Du, Yifan Sun et al.
*   A Comprehensive Energy-resolved Timing Analysis of XTE J1550-564
    Sidharth Chukka and Keigo Fukumura
*   Erratum: Stochastic spin flips in polariton condensates: nonlinear tuning from GHz to sub-Hz (2018 New J. Phys. 20 075008)
    Yago del Valle-Inclan Redondo, Hamid Ohadi, Yuri G Rubo et al.

[IMAGE: Advertisement for The Electrochemical Society (ECS) 249th ECS Meeting, May 24-28, 2026, Seattle, WA, US, with a submission deadline of December 5, 2025, and a 'Sustainable Technologies' logo.]

---
Saint Petersburg OPEN 2016
Journal of Physics: Conference Series 741 (2016) 012081
IOP Publishing
doi:10.1088/1742-6596/741/1/012081

**Post-processing procedure for industrial quantum**
**key distribution systems**

Evgeny Kiktenko$^{1,2}$, Anton Trushechkin$^{1,3}$, Yury Kurochkin$^4$, and
Aleksey Fedorov$^{1,4}$

$^1$ Theoretical Department, DEPHAN, 100A Novaya St., Skolkovo, Moscow 143025, Russia
$^2$ Bauman Moscow State Technical University, 5 2nd Baumanskaya St., Moscow 105005, Russia
$^3$ Steklov Mathematical Institute of Russian Academy of Sciences, 8 Gubkina St., Moscow
119991, Russia
$^4$ Russian Quantum Center, 100A Novaya St., Skolkovo, Moscow 143025, Russia

E-mail: akf@rqc.ru

**Abstract.** We present algorithmic solutions aimed on post-processing procedure for industrial
quantum key distribution systems with hardware sifting. The main steps of the procedure are
error correction, parameter estimation, and privacy amplification. Authentication of classical
public communication channel is also considered.

**1. Introduction**
Significant attention to quantum key distribution [1] is related to the fact of breaking of public-
key encryption algorithms using quantum computing. Security of public-key exchange schemes
can be justified on the basis of the complexity of several mathematical problems. Nevertheless,
the Shor's algorithm [2] allows solving these problems in a polynomial time. Absence of efficient
classical (non-quantum) algorithms breaking public-key cryptosystems still remains unproved.
In view of possibility to establish a shared private key with unconditional security between
two users (Alice and Bob) via quantum key distribution [1], using of information-theoretically
secure one-time-pad encryption technique becomes a practical tool. Privacy of quantum keys is
guaranteed by the laws of quantum physics [3]. Quantum key distribution has been realized in
experiments [5–9]. Devices for quantum key distribution are available on the market [10].
On the top of using of single quantum objects (photons) as information carriers, in quantum
key distribution protocols such as the seminal BB84 protocol [4] classical communications and
post-processing are required [4]. A key requirement for quantum key distribution is that classical
communications are not distorted. In other words, an eavesdropper is able to obtain information
from this channel, but cannot to change it. To this end, one can use authentication schemes.
Due to the technological limitations of quantum key distribution, keys of Alice and Bob are
initially different even in the absence of eavesdropping. Excluding of this effect can be realized
by using error correction procedures. On the basis of compassion of keys after error corrections,
one can estimate the quantum bit error rate (QBER). If QBER exceeds a critical value, the
parties receive warning message about possible eavesdropping. In other cases, they use privacy
amplification methods to exclude announced information on previous stages from keys.

Content from this work may be used under the terms of the Creative Commons Attribution 3.0 licence. Any further distribution
of this work must maintain attribution to the author(s) and the title of the work, journal citation and DOI.
Published under licence by IOP Publishing Ltd
1

---
Saint Petersburg OPEN 2016
Journal of Physics: Conference Series 741 (2016) 012081
IOP Publishing
doi:10.1088/1742-6596/741/1/012081

In this contribution, we report about the joint research project, which is aimed on a design of
an industrial fiber based quantum key distribution system in Russia in collaboration between four
teams. The quantum key distribution engine is based on the decoy states BB84 protocol [11]. We
present the developed post-processing procedure for sifted quantum keys (*i.e.*, keys after basis
and intensity reconciliations), which consists of the following steps: error correction, parameter
estimation, and privacy amplification. Communications over public channel are authenticated.
In Sec. 2, we briefly describe the hardware engine of our system. In Sec. 3, we consider post-
processing algorithms for error correction, parameter estimation, and privacy amplification. We
discuss authentication of public channel in Sec. 4. The workflow of the post-processing procedure
is presented in Sec. 5. We summarize our results in Sec. 6.

**2. Quantum key distribution setup**
Our setup for quantum key distribution consist of two modules on the each side (Alice and
Bob). First, control units, that are connected via the optical fiber and perform all operations
with photons. Second, conjugation units, that are connected with the classical public channel,
perform all post-processing, and export final keys to external applications.
Operation of the control units is based on the "plug and play" [12] principle of realization of
the BB84 protocol with decoy states [11]. Control units work as follows. Bob sends a sequence
("train") of strong coherent pulses to Alice. On her side these pulses are (i) reflected by a
Faraday mirror, (ii) phase modulated with four possible values according to random basis and
bit value, (iii) attenuated to the one of three intensities (vacuum, signal, or decoy), and (iv)
sent back. The scheme passively compensates slowly varying polarization fluctuations in the
fiber. In the Bob's control unit, the returned attenuated pulses are phase modulated with two
possible values that correspond to random choice of basis, and measured by pair of single photon
detectors.
After an each "train" of pulses, Bob's conjugation unit obtains time indices of detected signals
and corresponding bit and basis values. These time indices and values of basis choices are sent
to Alice's conjugation unit via classical channel. Alice compares the measurement bases with
preparation bases and sends Bob time indices of signal bits, which have been measured and
prepared in the same basis. This procedure is know as sifting. The values of signal qubits that
were prepared and measured in the same basis give so-called sifted keys, that we denote as $K_{\text{sift}}^A$
and $K_{\text{sift}}^B$. We note that Alice's conjugation unit also obtains rate of detection events for all three
intensities that are used for revealing of photon-number splitting attack. However, in this work
we restrict ourselves to post-processing without paying attention to analysis of decoy states.
We also note that random choices of bit values and preparation basis in Alice's control unit
and random choices of measurement bases in Bob's one are performed using random number
generators. Random number generators are important and often forgotten ingredient of quantum
key distribution systems [9]. Their development is a part of the project [13]. Random number
generator is used several times during the protocol: (i) to generate random photon states,
(ii) to choose random measurement bases, (iii) to generate random information specifying the
verification hash function (part of error correction) and the privacy amplification procedure.

**3. Algorithms for the post-processing procedure**
In this section, we consider processing procedures of two sifted quantum keys $K_{\text{sift}}^A$ and $K_{\text{sift}}^B$.

**3.1. Error correction**
The error correction algorithm is applied for making the sifted quantum keys $K_{\text{sift}}^A$ and $K_{\text{sift}}^B$ to
be identical on the both sides. We employ the following error correction algorithm with two basic
stages. The first is to use the low-density parity-check (LDPC) syndrome coding/decoding [14]

2

---
Saint Petersburg OPEN 2016
Journal of Physics: Conference Series 741 (2016) 012081
IOP Publishing
doi:10.1088/1742-6596/741/1/012081

to correct discrepancies between keys. The universal polynomial hashing [15] to verify an identity
between keys after previous step is used as the second stage.
Alice and Bob share a pool of LDPC parity-matrices with code-rates $R$ from 0.9 up to 0.5
(with step being equal to 0.05) and the frame size (length of processed strings) being equal to
$n = 4096$. These matrices are constructed with progressive edge-growth algorithm [16] using
polynomial (degree distributions) from Ref. [17]. For each coding and decoding process parties
employ code with the minimal rate $R$, which satisfies the following condition:

$$
\frac{1-R}{h_b (\text{QBER}_{\text{est}})} < f_{\text{crit}}
\quad (1)
$$

where $h_b$ is the standard binary entropy function, $\text{QBER}_{\text{est}}$ is the estimated level of QBER (see
below), and $f_{\text{crit}} = 1.22$ is the critical efficiency parameter in our setup, that is the tolerable
ratio between level of disclosed information about sifted key and theoretical limit for successive
error correction, which is predicted by the classical information theory.
To decrease a frame error rate (probability of unsuccessive decoding) in the constraint that
the resulting efficiency is not greater than $f_{\text{crit}}$, Alice and Bob use the shortening technique [18].
The number of shortened bits $n_s$ is obtained from the following expression

$$
n_s = \left\lfloor n - \frac{m}{f_{\text{crit}} h_b (\text{QBER}_{\text{est}})} \right\rfloor,
\quad (2)
$$

where $\lfloor x \rfloor$ stands for the maximal integer less than $x$. Alice and Bob construct $N = 256$ strings
of length $n$ possessing $n - n_s$ bits of their sifted keys $K_{\text{sift}}^A$ and $K_{\text{sift}}^B$ and $n_s$ shortened bits,
whose positions and values come from synchronised pseudo-random generator. Bob multiplies
the chosen parity-check matrix on the constructed strings to obtain syndromes that are sent to
Alice. For the LDPC syndrome decoding, Alice applies iterative sum-product algorithm [18],
which uses log-likelihood ratios for messages between symbol and parity-check nodes of the
corresponding Tanner graph. To avoid costly calculations, we employ optimization techniques
considered in Ref. [19]. Then Alice removes shortened bits obtaining corrected key.
If the algorithm of decoding does not converge for particular block in a specified number of
iterations (we use about 60 iterations in our setup), then this block is considered as unverified.
However, rarely decoding process converges to a wrong result, *i.e.*, to a incorrect key but still
with proper syndrome. To avoid such situations, the second step of verification is used for blocks
successively completed decoding.
In our setup, we employ comparison of hash-tags constructed with $\epsilon$-universal polynomial
hashing [15]. In particular, we use modified 50-bit variant of PolyR hash function that provide
collision probability for a $N$ blocks of $n - n_s$ bits on the level of $\epsilon_{\text{ver}} < 2 \times 10^{-12}$. If the hash
tags on the both sides match, then the corresponding blocks are concerned to be identical on
the both sides and are added to verified keys $K_{\text{ver}}$. We note that $K_{\text{ver}}$ is a part of $K_{\text{sift}}^B$ as all
modifications of the key are performed on the Alice's side.

**3.2. Parameter estimation**
The purpose of the parameter estimation procedure is to determine QBER that is a probability
of bit-flipping in a quantum channel. This problem could be resolved by comparison of input
$K_{\text{sift}}^A$ and output $K_{\text{ver}}$ keys of the error correction, because as it was noted all changes of the key
were performed exclusively by Alice. The ratio of corrected bits is averaged over a set of $N$ the
error correction blocks, and for unverified blocks a conservative maximal value $1/2$ is assumed.
If we denote all verified blocks in the set as $V$ than the estimated QBER reads

$$
\text{QBER}_{\text{est}} = N^{-1} \left( \sum_{i \in V} \text{QBER}_i + \left| \bar{V} \right| / 2 \right),
\quad (3)
$$

where $\text{QBER}_i$ is the ratio of bit-flips in $i$th block and $|\bar{V}|$ is number on unverified blocks.

3

---
Saint Petersburg OPEN 2016
Journal of Physics: Conference Series 741 (2016) 012081
IOP Publishing
doi:10.1088/1742-6596/741/1/012081

**3.3. Privacy amplification**
After these procedures, both sides have identical bit strings. Nevertheless, Eve may have some
amount of information about them. The privacy amplification procedure is used to reduce this
potential information of an adversary to a negligible quantity. This is achieved by a contraction
of the input bit string into a shorter string. The output shorter string is a final private key $K_{\text{sec}}$
of length $l_{\text{sec}}$. Our algorithm of the privacy amplification firstly checks (according to Ref. [20])
whether it is possible to distill private key with the given length and security parameter $\epsilon_{\text{pa}}$
(which is set to $\epsilon_{\text{pa}} = 10^{-12}$). Namely, define the quantity

$$
\nu = \sqrt{\frac{2(l_{\text{ver}} + k)(k + 1) \ln \frac{1}{\epsilon_{\text{pa}}}}{l_{\text{ver}} k^2}}
\quad (4)
$$

where $k$ in the number of bits used to estimate the QBER. Then if the inequality

$$
2^{-(l_{\text{ver}}(1-h_b(\delta+\nu))-r-t-l_{\text{sec}})} \le \epsilon_{\text{pa}}
\quad (5)
$$

is satisfied, then the generation of a private key of length $l_{\text{sec}}$ and security parameter $\epsilon_{\text{pa}}$ is
possible. Here $r$ is the total length of the syndromes in the error correction procedure, $t$ is the
total length of the verification hashes and $\delta$ is a critical level of QBER.
If formula (5) gives the positive answer on the question about the possibility of key generation
with the desired parameters, then the final private key is computed as a hash function of the input
bit string. The family of hash functions is required to be 2-universal [20]. The generalization to
almost universal families of hash functions is also possible.
A hash function is chosen randomly from the Toeplitz universal family of hash functions [21].
A matrix $T$ of dimensionality $l_{\text{sec}} \times l_{\text{ver}}$ is a Toeplitz matrix if $T_{i,j} = T_{i+1,j+1} = S_{j-i}$ for all
$i = 1, \ldots, l_{\text{sec}} - 1$ and $j = 1, \ldots, l_{\text{ver}} - 1$. Thus, to generate a Toeplitz matrix, we need a random
bit string $S = (s_{1-l_{\text{sec}}}, s_{1-l_{\text{sec}}+1}, \ldots, s_{l_{\text{ver}}-1})$ of length $l_{\text{ver}} + l_{\text{sec}} - 1$. The string $S$ is generated
randomly by one side (say, Alice) and sent to another side (Bob) by public channel. Let us
denote the corresponding Toeplitz matrix as $T_S$. Then the final private key is computed as
$K_{\text{sec}} = T_S K_{\text{ver}}$ (with multiplication and addition modulo 2).
It is possible to use not a random, but a pseudo-random bit string, which uses a shorter
random seed, to specify the Toeplitz matrix [21, 22]. In this case, the family of hash functions
is not universal, but almost universal, which is also acceptable for privacy amplification with
some modifications in formula (5). The security of privacy amplification is based on the Leftover
hash lemma, which can be proved for almost universal hash functions as well [23]. However,
neither the rate of random number generator, nor the amount of publicly amount information
are critical parameters of our setup. Thus, we adopt the standard family of Topelitz functions.

**4. Authentication**
The purpose of the authentication is to ensure that messages received by each side via public
channel were sent by the other legitimate side (not by the adversary) and were not changed
during the transmission.
Usual way to deal with this problem is hashing of the messages by hash functions dependent
on a private key $K_{\text{aut}}$ known only to legitimate parties. In general, the procedure is as follows:
Alice sends to Bob a message with the hash tag. After receiving the message, Bob also computes
the hash tag of the message and compare it to that received from Alice. If the hash tags
coincide, Bob acknowledge the message as sent by Alice, otherwise he breaks the protocol. The
hash function requires to assure that, whenever an eavesdropper does not know the private key,
he cannot modify the message or send his own message and guess the correct hash tag of the
message except for negligible probability (we require it not to exceed $\epsilon_{\text{aut}} = 10^{-12}$).

4

---
Saint Petersburg OPEN 2016
Journal of Physics: Conference Series 741 (2016) 012081
IOP Publishing
doi:10.1088/1742-6596/741/1/012081

For unconditional security, the hash function must be chosen from some universal family:
almost strongly universal [24,25], almost xor-universal [21,26], or almost $\Delta$-universal family [27].
After consideration of many universal families of hash functions, we have decided in favour
of the Toeplitz hashing (see Sec. 3.3 above) due to its computational simplicity. In the privacy
amplification procedure, we exploit that it is a 2-universal family. Here we exploit its xor-
universality [21]. Let the lengths of the authenticated messages and their hash tags be $l_M$ and
$l_h$ respectively. The hash tag of the $i$th message $M_i$ is calculated as

$$
h(M_i) = T_S M_i \oplus r_i,
\quad (6)
$$

where $T_S$ is a $l_h \times l_M$ Toeplitz matrix generated by a string $S$ of length $l_h + l_M - 1$, $r_i$ is a
bit string of length $l_h$, and $\oplus$ is the bitwise xor. Both $S$ and $r_i$ are private and taken from the
common private key $K_{\text{aut}}$. Then, the probability that an eavesdropper will guess the hash tag
of a modified message is not more than $2^{-l_h}$. The demand $\epsilon_{\text{aut}} = 10^{-12}$ gives $l_h = 40$.
As in privacy amplification, we do not adopt a pseudo-random generation of a string $S$ from
a shorter string. This reduces the consumption rate of the private key. However, formula (6)
allows to generate the bit string $S$ only once, for the first message. For further messages, the
private key is consumed in the rate $l_h$ bits per message (for strings $r_i$). Thus, large initial
consumption of the private is not critical. The string $S$ may be used for many sessions of
quantum key distribution.
Also this consideration suggests that it is advantageous to authenticate several messages at
once: except for the first message, the consumption of the private key is $l_h$ bit per message
and does not depend on the length of the message. However, the reduction of the number of
authentications raises the risk of denial-of-service attacks from an eavesdropper: he is able
to simulate messages from legitimate parties and force them to do calculations before his
interference will be disclosed (in the nearest authentication stage). Thus, there is a trade-off
between the private key consumption rate and the risk of denial-of-service attacks.
During the post-processing, the public classical channel is used twice: (i) to send the syndrome
in the error correction stage along with the verification hash tag and (ii) to send the decision
about possibility of key generation and (if the answer is positive) estimated level of QBER and
bit string used to generate the Toeplitz matrix in the privacy amplification algorithm.
Another possibility is to use the hash function based on the known GOST cipher [28], though
it is not unconditionally secure.

**5. Workflow of the post-processing procedure**
The workflow of the post-processing procedure is as follows. Sifted keys go through the error
correction that is adjusted on the current value of QBER. After accumulation of necessary
number of blocks they input to the parameter estimation (together with their versions before
the error correction). If an estimated value of QBER given by (3) is higher than the critical value
needed for efficient privacy amplification, the parties receive warning message about possible of
eavesdropping. Otherwise, verified blocks input privacy amplification and estimated QBER is
used in next round of the error correction algorithm.
The overall (in)security parameter of the quantum key distribution system is

$$
\epsilon_{\text{QKD}} = \epsilon_{\text{ver}} + \epsilon_{\text{pa}} + \epsilon_{\text{aut}} = 2 \times 10^{-11} + 10^{-12} + 10^{-12} < 3 \times 10^{-11}.
\quad (7)
$$

This parameter majorizes both the probability that the keys of Alice and Bob do not coincide
and the probability of guessing the common key by Eve. If this parameter exceeds a critical
value, then the protocol is terminated.
After the privacy amplification procedure, a fraction of the key is used for authentication in
the next rounds. In our setup, the fraction of generated private key consumed by authentication
procedure does not exceed 15%.

5

---
Saint Petersburg OPEN 2016
Journal of Physics: Conference Series 741 (2016) 012081
IOP Publishing
doi:10.1088/1742-6596/741/1/012081

**6. Conclusion**
We have present post-processing procedure for industrial quantum key distribution systems.
The post-processing procedure consisting of error correction, parameter estimation, and privacy
amplification has been described. Also authentication of classical communications over a public
channel has been considered.

**Acknowledgments**
We thank Andrey Fedchenko for useful comments. The support from Ministry of Education
and Science of the Russian Federation in the framework of the Federal Program (Agreement
14.579.21.0104, ID RFMEFI57915X0104) is acknowledged. We thank the organizers of the 3rd
International School and Conference Saint-Petersburg OPEN 2016 for kind hospitality.

**References**
[1] For a review, see Gisin N, Ribordy G, Tittel W, and Zbinden H 2002 *Rev. Mod. Phys.* **74** 145; Scarani V,
Bechmann-Pasquinucci H, Cerf N J, Dusek M, Lütkenhaus N, and Peev M 2009 *Rev. Mod. Phys.* **81** 1301
[2] Shor P W 1997 *SIAM J. Comput.* **26** 1484
[3] Wootters W K and Zurek W H 1982 *Nature* **299** 802
[4] Bennet C H and Brassard G 1984 *Proceedings of IEEE International Conference on Computers, Systems and*
*Signal Processing* (Bangalore, India, 1984) p. 175 (New York: IEEE)
[5] Bennett C H, Bessette F, Salvail L, Brassard G, and Smolin J 1992 *J. Cryptol.* **5** 3
[6] Gobby C, Yuan Z L, and Shields A J 2004 *Appl. Phys. Lett.* **84** 3762
[7] Schmitt-Manderbach T, Weier H, Fürst M, Ursin R, Tiefenbacher F, Scheidl T, Perdigues J, Sodnik Z,
Kurtsiefer C, Rarity J G, Zeilinger A, and Weinfurter H 2007 *Phys. Rev. Lett.* **98** 010504
[8] Stucki D, Walenta N, Vannel F, Thew R T, Gisin N, Zbinden H, Gray S, Towery C R, and Ten S 2009 *New*
*J. Phys.* **11** 075003
[9] Walenta N, Burg A, Caselunghe D, Constantin J, Gisin N, Guinnard O, Houlmann R, Junod P, Korzh B,
Kulesza N, Legré M, Lim C W, Lunghi T, Monat L, Portmann C, Soucarros M, Thew R T, Trinkler P,
Trolliet G, Vannel F, and Zbinden H 2014 *New J. Phys.* **16** 013047
[10] Characteristics of devices from ID Quantique (Switzerland), SeQureNet (France), and Austrian Institute of
Technology (Austria) are available on their websites.
[11] Lo H-K, Ma X, and Chen K 2005 *Phys. Rev. Lett.* **94** 230504; Zhao Y, Qi B, Ma X, Lo H-K, and Qian L
2006 *Phys. Rev. Lett.* **96** 070502
[12] Muller A, Herzog T, Huttner B, Tittel W, Zbinden H, and Gisin N 1997 *Appl. Phys. Lett.* **70** 793-5
[13] Chizhevsky V N 2010 *Phys. Rev. E* **82** 050101
[14] Gallager R 1962 *Inf. Theory, IRE Trans.* **8** 21; MacKay D 1999 *IEEE Trans. Inf. Theory.* **45** 399
[15] Krovetz T and Rogaway P 2000 *Lect. Notes Comp. Sci.* **2015** 73
[16] Martinez-Mateo J, Elkouss D, and Martin V 2010 *IEEE Commun. Lett.* **14** 1155
[17] Elkouss D, Leverrier A, Alléaume R, and Boutros J 2009 *Proceedings of IEEE International Symposium*
*Information Theory* (Seoul, South Korea, 2009) p. 1879 (New York: IEEE)
[18] Elkouss D, Martinez-Mateo J, and Martin V 2011 *Quant. Inf. Comput.* **11** 0226
[19] Hu X-Y, Eleftheriou E, Arnold D M, and Dholakia A 2001 *Proceedings of IEEE Global Telecommunications*
*Conference* (San Antonio, USA, 2001) **2** 1036 (New York: IEEE)
[20] Tomamichel M and Leverrier A 2015 *arXiv:1506.08458*
[21] Krawczyk H 1994 *Lect. Notes Comp. Sci.* **839** 129
[22] Krawczyk H 1995 *Lect. Notes Comp. Sci.* **921** 301
[23] Tomamichel M, Schaffner C, Smith A, and Renner R 2011 *IEEE Trans. Inf. Theor.* **57** 5524
[24] Wegman M N and Carter J L 1981 *J. Comp. Syst. Sci.* **22** 265
[25] Stinson D R 1992 *Lect. Notes Comp. Sci.* **576** 74
[26] Shoup V 1996 *Lect. Notes Comp. Sci.* **1109** 313
[27] Halevi S and Krawczyk H 1997 *Lect. Notes Comp. Sci.* **1267** 172
[28] Schneier B 1996 *Applied Cryptography* (John Wiley & Sons, Inc.)s