from inverted.test2_artifacts import Test2ArtifactWriter


def test_test2_artifact_writer_is_not_a_pytest_test_class():
    assert getattr(Test2ArtifactWriter, "__test__", True) is False
