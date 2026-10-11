"""Portable public tests; no private firmware or network is required."""
import io, json, pathlib, tempfile, unittest
from unittest import mock
from PIL import Image
import core, journal, prepare_private, server

class PublicTests(unittest.TestCase):
    def test_color_preserves_alpha_and_red_zone(self):
        im=Image.new('RGBA',(4,1));im.putdata([(255,255,255,200),(240,20,5,255),(45,80,99,0),(90,120,180,127)])
        result=core.decode(core.transform(core.png(im),{'color':'#32c880'},color_only=True))
        self.assertEqual(result.getpixel((1,0)),im.getpixel((1,0)))
        self.assertEqual(result.getpixel((2,0)),im.getpixel((2,0)))
        self.assertEqual(result.getchannel('A').tobytes(),im.getchannel('A').tobytes())
        self.assertEqual(result.getpixel((0,0)),(50,200,128,200))

    def test_crop_and_palette(self):
        raw=core.png(Image.new('RGBA',(100,50),(20,60,110,255)))
        for fit in ('cover','contain','stretch'):
            out=core.convert_image(raw,[60,80],fit,colors=64);self.assertEqual(out.size,(60,80))

    def test_color_only_rejects_image_and_opacity(self):
        for part in ('speed','rpm_numbers','rpm_accent'):
            for option in ({'mode':'image'},{'opacity':20}):
                with self.assertRaises(ValueError):core.validate_config({'parts':{part:option}})

    def test_import_rejects_wrong_firmware_without_files(self):
        with tempfile.TemporaryDirectory() as name:
            root=pathlib.Path(name);source=root/'wrong';source.write_bytes(b'not firmware');destination=root/'private'
            with self.assertRaises(ValueError):prepare_private.prepare(source,destination=destination)
            self.assertFalse(destination.exists())

    def test_private_path_must_be_external(self):
        with self.assertRaises(ValueError):prepare_private.prepare('missing',destination=core.BASE/'private')

    def test_unconfigured_setup_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(core,'PRIVATE',pathlib.Path(directory)):
            core.stock.cache_clear()
            ready,message=core.readiness();self.assertFalse(ready);self.assertIn('prepare_private.py',message)
            core.stock.cache_clear()

    def test_asset_path_traversal_rejected(self):
        with self.assertRaises(ValueError):core.asset_file('../../core.py')

    def test_atomic_journal_keeps_previous_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            file=pathlib.Path(directory)/'state.json';journal.write_json(file,{'ok':1})
            with mock.patch.object(journal.os,'replace',side_effect=OSError('full')):
                with self.assertRaises(OSError):journal.write_json(file,{'ok':2})
            self.assertEqual(json.loads(file.read_text()),{'ok':1});self.assertEqual(list(file.parent.glob('*.tmp')),[])

    def test_jobs_recover_without_device_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);journal.write_json(root/'jobs.json',{'a':{'id':'a','kind':'device-install','status':'running'}})
            with mock.patch('socket.create_connection',side_effect=AssertionError('No vehicle access allowed')):
                studio=server.Studio(root,root/'exports');self.assertEqual(studio.jobs['a']['status'],'interrupted')

    def test_public_samples_are_generated_and_decodable(self):
        for name,kind in [('example-wallpaper.png','PNG'),('example-animation.gif','GIF')]:
            with Image.open(core.BASE/'assets'/name) as im:
                self.assertEqual(im.format,kind);self.assertEqual(im.size,(1024,600));im.load()
if __name__=='__main__':unittest.main()
