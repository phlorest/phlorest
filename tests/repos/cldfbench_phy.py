import pathlib

from phlorest import Dataset


class DS(Dataset):
    dir = pathlib.Path(__file__).parent
    id = 'phy'

    def cmd_makecldf(self, args):
        self.init(args)
        args.writer.add_summary(
            self.raw_dir.read_tree('nexus.trees'),
            self.metadata,
            args.log
        )
