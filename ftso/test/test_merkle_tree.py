# TODO: this should be a test for the merkle tree class (in lib)


from django.test import TestCase

from processing.merkle_tree import MerkleTree


class MerkleTreeTestCase(TestCase):
    def test_examples(self):
        SCENARIOS = [
            {
                "elements": ["0xabf1118796", "0x465afec45b"],
                "expectedRoot": "0x3542843c98b2d247a96f53d8d6af8484fb6eb91efaccf5cee404a7f2845ed061",
            },
            {
                "elements": ["0xabf1118796", "0x465afec45b", "0x94aafe1267"],
                "expectedRoot": "0x27c1f8bd1f33751289bb92c3fd7f7ee5e5c5163c818d7370578897b0d50bbac3",
            },
            {
                "elements": ["0x1", "0x2", "0x3", "0x4"],
                "expectedRoot": "0x0c48ddc2b8d6d066c52fc608d4d0254f418bea6cd8424fe95390ac87323f9c9f",
            },
            {
                "elements": ["0x1", "0x2", "0x3", "0x4", "0x5", "0x6", "0x7", "0x8"],
                "expectedRoot": "0xca06f8324669a77a3ef9a7bcf15421d7bb5618a79dbe5590117ba5f5a4e72bc1",
            },
        ]

        for scenario in SCENARIOS:
            elements = scenario["elements"]
            root = scenario["expectedRoot"]
            tree = MerkleTree(elements)
            self.assertEqual(tree.root, root)

    def test_proofs_gen(self):
        TREES = [
            [
                {
                    "element": "0xabf1118796",
                    "proof": ["0x000000000000000000000000000000000000000000000000000000465afec45b"],
                },
                {
                    "element": "0x465afec45b",
                    "proof": ["0x000000000000000000000000000000000000000000000000000000abf1118796"],
                },
            ],
            [
                {
                    "element": "0x1",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000002",
                        "0x2e174c10e159ea99b867ce3205125c24a42d128804e4070ed6fcc8cc98166aa0",
                        "0x027d4202008bf9d080d976936bdbedf33e9934bc0b1745fd5712497536a83bd9",
                    ],
                },
                {
                    "element": "0x2",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000001",
                        "0x2e174c10e159ea99b867ce3205125c24a42d128804e4070ed6fcc8cc98166aa0",
                        "0x027d4202008bf9d080d976936bdbedf33e9934bc0b1745fd5712497536a83bd9",
                    ],
                },
                {
                    "element": "0x3",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000004",
                        "0xe90b7bceb6e7df5418fb78d8ee546e97c83a08bbccc01a0644d599ccd2a7c2e0",
                        "0x027d4202008bf9d080d976936bdbedf33e9934bc0b1745fd5712497536a83bd9",
                    ],
                },
                {
                    "element": "0x4",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000003",
                        "0xe90b7bceb6e7df5418fb78d8ee546e97c83a08bbccc01a0644d599ccd2a7c2e0",
                        "0x027d4202008bf9d080d976936bdbedf33e9934bc0b1745fd5712497536a83bd9",
                    ],
                },
                {
                    "element": "0x5",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000006",
                        "0x24cd397636bedc6cf9b490d0edd57c769c19b367fb7d5c2344ae1ddc7d21c144",
                        "0x0c48ddc2b8d6d066c52fc608d4d0254f418bea6cd8424fe95390ac87323f9c9f",
                    ],
                },
                {
                    "element": "0x6",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000005",
                        "0x24cd397636bedc6cf9b490d0edd57c769c19b367fb7d5c2344ae1ddc7d21c144",
                        "0x0c48ddc2b8d6d066c52fc608d4d0254f418bea6cd8424fe95390ac87323f9c9f",
                    ],
                },
                {
                    "element": "0x7",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000008",
                        "0xbfd358e93f18da3ed276c3afdbdba00b8f0b6008a03476a6a86bd6320ee6938b",
                        "0x0c48ddc2b8d6d066c52fc608d4d0254f418bea6cd8424fe95390ac87323f9c9f",
                    ],
                },
                {
                    "element": "0x8",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000007",
                        "0xbfd358e93f18da3ed276c3afdbdba00b8f0b6008a03476a6a86bd6320ee6938b",
                        "0x0c48ddc2b8d6d066c52fc608d4d0254f418bea6cd8424fe95390ac87323f9c9f",
                    ],
                },
            ],
            [
                {
                    "element": "0x1",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000002",
                        "0x2e174c10e159ea99b867ce3205125c24a42d128804e4070ed6fcc8cc98166aa0",
                    ],
                },
                {
                    "element": "0x2",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000001",
                        "0x2e174c10e159ea99b867ce3205125c24a42d128804e4070ed6fcc8cc98166aa0",
                    ],
                },
                {
                    "element": "0x3",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000004",
                        "0xe90b7bceb6e7df5418fb78d8ee546e97c83a08bbccc01a0644d599ccd2a7c2e0",
                    ],
                },
                {
                    "element": "0x4",
                    "proof": [
                        "0x0000000000000000000000000000000000000000000000000000000000000003",
                        "0xe90b7bceb6e7df5418fb78d8ee546e97c83a08bbccc01a0644d599ccd2a7c2e0",
                    ],
                },
            ],
            [
                {
                    "element": "0xabf1118796",
                    "proof": [
                        "0x00000000000000000000000000000000000000000000000000000094aafe1267",
                        "0x000000000000000000000000000000000000000000000000000000465afec45b",
                    ],
                },
                {
                    "element": "0x465afec45b",
                    "proof": ["0x90864c6352acbe9b381ebb10a939ef12be7ffc44e7730918199c567b61b2259b"],
                },
                {
                    "element": "0x94aafe1267",
                    "proof": [
                        "0x000000000000000000000000000000000000000000000000000000abf1118796",
                        "0x000000000000000000000000000000000000000000000000000000465afec45b",
                    ],
                },
            ],
        ]

        for TREE in TREES:
            tree = MerkleTree([el["element"] for el in TREE])
            for el in TREE:
                proof = tree.get_proof(el["element"])
                self.assertEqual(proof, el["proof"])
